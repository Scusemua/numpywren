#
# Copyright 2018 PyWren Team
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

from __future__ import print_function

import os
import base64
import shutil
import json
import sys
import traceback
import time
import redis  
import boto3
from botocore.vendored.requests.packages.urllib3.exceptions import ReadTimeoutError

from six.moves import cPickle as pickle
from tblib import pickling_support

print("HELLO FROM JOBRUNNER")

pickling_support.install()
BACKOFF = 1
MAX_TRIES = 5

def b64str_to_bytes(str_data):
    str_ascii = str_data.encode('ascii')
    byte_data = base64.b64decode(str_ascii)
    return byte_data

# initial output file in case job fails
output_dict = {'result' : None,
               'success' : False}

print("JobRunner is executing!")

pickled_output = pickle.dumps(output_dict)
jobrunner_config_filename = sys.argv[1]

jobrunner_config = json.load(open(jobrunner_config_filename, 'r'))

# Need to change in wrenhandler.py, wrenconfig.py, matrix.py, matrix_utils.py, jobrunner.py.
redis_client = redis.StrictRedis(host = "ec2-18-208-217-26.compute-1.amazonaws.com", port = 6379)

# FIXME someday switch to storage handler
# download the func data into memory
s3_client = boto3.client("s3")

func_bucket = jobrunner_config['func_bucket']
func_key = jobrunner_config['func_key']

data_bucket = jobrunner_config['data_bucket']
data_key = jobrunner_config['data_key']
data_byte_range = jobrunner_config['data_byte_range']

output_bucket = jobrunner_config['output_bucket']
output_key = jobrunner_config['output_key']

storage_config = jobrunner_config["storage_config"]

## Jobrunner stats are fieldname float
jobrunner_stats_filename = jobrunner_config['stats_filename']
# open the stats filename
stats_fid = open(jobrunner_stats_filename, 'w')

def write_stat(stat, val):
    stats_fid.write("{} {:f}\n".format(stat, val))
    stats_fid.flush()

def get_object_with_backoff(s3_client, bucket, key, max_tries=MAX_TRIES, backoff=BACKOFF, **extra_get_args):
    num_tries = 0
    while (num_tries < max_tries):
        try:
            print("Attempting to get data from S3 bucket {} at key {}.".format(bucket, key))
            func_obj_stream = s3_client.get_object(Bucket=bucket, Key=key, **extra_get_args)
            break
        except ReadTimeoutError:
            time.sleep(backoff)
            backoff *= 2
            num_tries += 1
    return func_obj_stream

def get_object_with_backoff_redis(key, max_tries=MAX_TRIES, backoff=BACKOFF, **extra_get_args):
    num_tries = 0
    while (num_tries < max_tries):
        try:
            print("[JobRunner] Reading data from Redis at key \"{}\".".format(key))
            #func_obj_stream = s3_client.get_object(Bucket=bucket, Key=key, **extra_get_args)
            func_obj_stream = redis_client.get(key) 
            break
        except Exception:
            print("[JobRunner - WARNING] Failed to retrieve data from Redis at key \"{}\".".format(key))
            time.sleep(backoff)
            backoff *= 2
            num_tries += 1
    return func_obj_stream

try:
    func_download_time_t1 = time.time()

    print("Attempting to download func_obj_stream from Redis...")

    if storage_config['storage_backend'] == 's3':
        func_obj_stream = get_object_with_backoff(s3_client, bucket=func_bucket, key=func_key)
        print("Successfully downloaded. Attempting to load/deserialize data retrieved from S3.")
        obj = func_obj_stream['Body'].read()
        
        print("Successfully streamed. Attempting to deserialize data retrieved from S3.")
        loaded_func_all = pickle.loads(obj)
        
        func_download_time_t2 = time.time()
        write_stat('func_download_time',
                   func_download_time_t2-func_download_time_t1)        
    else:
        func_obj_stream = get_object_with_backoff_redis(key=func_key)
        print("Successfully downloaded. Attempting to load/deserialize data retrieved from Redis.")
        loaded_func_all = pickle.loads(func_obj_stream)

    print("Data loaded (deserialized) successfully!")
    func_download_time_t2 = time.time()
    write_stat('func_download_time',
               func_download_time_t2-func_download_time_t1)

    # save modules, before we unpickle actual function
    PYTHON_MODULE_PATH = jobrunner_config['python_module_path']

    print("PYTHON_MODULE_PATH = {}".format(PYTHON_MODULE_PATH))

    shutil.rmtree(PYTHON_MODULE_PATH, True) # delete old modules
    print("Deleted old modules located at {}".format(PYTHON_MODULE_PATH))
    os.mkdir(PYTHON_MODULE_PATH)
    print("Created new directory at {}".format(PYTHON_MODULE_PATH)) 
    sys.path.append(PYTHON_MODULE_PATH)
    print("Added newly-created directory {} to system path.".format(PYTHON_MODULE_PATH))

    for m_filename, m_data in loaded_func_all['module_data'].items():
        #print("Processing module data with filename {}".format(m_filename))
        m_path = os.path.dirname(m_filename)

        if len(m_path) > 0 and m_path[0] == "/":
            m_path = m_path[1:]
        to_make = os.path.join(PYTHON_MODULE_PATH, m_path)
        try:
            os.makedirs(to_make)
        except OSError as e:
            if e.errno == 17:
                pass
            else:
                raise e
        full_filename = os.path.join(to_make, os.path.basename(m_filename))
        #print "creating", full_filename
        with open(full_filename, 'wb') as fid:
            fid.write(b64str_to_bytes(m_data))

    # logger.info("Finished wrting {} module files".format(len(d['module_data'])))
    # logger.debug(subprocess.check_output("find {}".format(PYTHON_MODULE_PATH), shell=True))
    # logger.debug(subprocess.check_output("find {}".format(os.getcwd()), shell=True))

    # now unpickle function; it will expect modules to be there
    loaded_func = pickle.loads(loaded_func_all['func'])

    print("Loaded function.")
    print("loaded_func = {}".format(loaded_func))

    extra_get_args = {}
    if data_byte_range is not None:
        range_str = 'bytes={}-{}'.format(*data_byte_range)
        extra_get_args['Range'] = range_str

    print("Getting data from Redis.")
    data_download_time_t1 = time.time()
    if storage_config['storage_backend'] == 's3':
        data_obj_stream = get_object_with_backoff(s3_client, bucket=data_bucket,
                                                  key=data_key,
                                                  **extra_get_args)
        print("Got data from S3. Trying to deserialize it now.")                                          
        loaded_data = pickle.loads(data_obj_stream['Body'].read())
        data_download_time_t2 = time.time()
        write_stat('data_download_time',data_download_time_t2-data_download_time_t1)        
    else:
        data_obj_stream = get_object_with_backoff_redis(key=data_key)    
        print("Got data from S3. Trying to deserialize it now.")                                          
        # FIXME make this streaming
        loaded_data = pickle.loads(data_obj_stream['Body'].read())
        print("Deserialized data successfully.")
        data_download_time_t2 = time.time()
        write_stat('data_download_time',data_download_time_t2-data_download_time_t1)
        if data_byte_range is not None:
            print("We only want bytes {} through {} (inclusive) of the object...".format(data_byte_range[0], data_byte_range[1]))
            data_obj_stream = data_obj_stream[data_byte_range[0]:data_byte_range[1] + 1] # INCLUSIVE

        print("Got data from Redis. Trying to deserialize it now.")
        loaded_data = pickle.loads(data_obj_stream)
        data_download_time_t2 = time.time()
        write_stat('data_download_time',data_download_time_t2-data_download_time_t1)

    print("Executing function now...")
    y = loaded_func(loaded_data)
    print("Function executed successfully!")
    output_dict = {'result' : y,
                   'success' : True,
                   'sys.path' : sys.path}
    pickled_output = pickle.dumps(output_dict)

except Exception as e:
    print("[ERROR] Encountered exception.\n{}".format(e))
    exc_type, exc_value, exc_traceback = sys.exc_info() # Creates circular reference!
    print("Traceback:")
    traceback.print_tb(exc_traceback)

    print("Exeception Type: {}\nException Value: {}\nTraceback: {}".format(exc_type, exc_value, exc_traceback))

    # Shockingly often, modules like subprocess don't properly
    # call the base Exception.__init__, which results in them
    # being unpickleable. As a result, we actually wrap this in a try/catch block
    # and more-carefully handle the exceptions if any part of this save / test-reload
    # fails
    try:
        pickled_output = pickle.dumps({'result' : e,
                                       'exc_type' : exc_type,
                                       'exc_value' : exc_value,
                                       'exc_traceback' : exc_traceback,
                                       'sys.path' : sys.path,
                                       'success' : False})

        # this is just to make sure they can be unpickled
        pickle.loads(pickled_output)

    except Exception as pickle_exception:
        print("[WARNING] Pickle exception encountered!")
        pickled_output = pickle.dumps({'result' : str(e),
                                       'exc_type' : str(exc_type),
                                       'exc_value' : str(exc_value),
                                       'exc_traceback' : exc_traceback,
                                       'exc_traceback_str' : str(exc_traceback),
                                       'sys.path' : sys.path,
                                       'pickle_fail' : True,
                                       'pickle_exception' : pickle_exception,
                                       'success' : False})
finally:
    output_upload_timestamp_t1 = time.time()
    if storage_config['storage_backend'] == 's3':
        print("Storing output/result/data in S3 at key \"{}\".".format(output_key))
        s3_client.put_object(Body=pickled_output,
                             Bucket=output_bucket,
                             Key=output_key)
        output_upload_timestamp_t2 = time.time()
        write_stat("output_upload_time", output_upload_timestamp_t2 - output_upload_timestamp_t1)                             
    elif storage_config['storage_backend'] == 'redis':
        print("Storing output/result/data in Redis at key \"{}\".".format(output_key))
        redis_client.set(output_key, pickled_output)
        output_upload_timestamp_t2 = time.time()
        write_stat("output_upload_time", output_upload_timestamp_t2 - output_upload_timestamp_t1)
