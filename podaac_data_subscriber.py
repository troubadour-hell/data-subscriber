#!/usr/bin/env python3

# # Access Sentinel-6 MF Data using a script
# This script shows a simple way to maintain a local time series of Sentinel-6  data using the [CMR Search API](https://cmr.earthdata.nasa.gov/search/site/docs/search/api.html). It downloads granules the ingested since the previous run to a designated data folder and overwrites a hidden file inside with the timestamp of the CMR Search request on success.
# Before you beginning this tutorial, make sure you have an Earthdata account: [https://urs.earthdata.nasa.gov] .
# Accounts are free to create and take just a moment to set up.


import urllib
from urllib import request
from http.cookiejar import CookieJar
import getpass
import netrc
import requests
import json
import socket
import sys
import argparse
import datetime

__version__ = "1.0"


## TODO: ???
def validate(args):
    bounds = args.bbox.split(',')
    for b in bounds:
        try:
            float(b)
        except:
            raise ValueError("Error parsing '--bounds': " + args.bbox + ". Format is W Longitude,S Latitude,E Longitude,N Latitude without spaces ")

    if args.dataSince:
        try:
            datetime.strptime(args.dataSince, '%Y-%m-%dT%H:%M:%SZ')
        except ValueError as ve:
            raise ValueError("Error parsing '--data-since' date: " + args.dataSince + ". Format must be like 2021-01-14T00:00:00Z")

    if args.minutes:
        try:
            int(args.minutes)
        except:
            raise ValueError("Error parsing '--minutes': " + args.minutes + ". Number must be an integer.")





###############The lines below are to get the IP address. You can make this static and assign a fixed value to the IPAddr variable
hostname = socket.gethostname()
IPAddr = "127.0.0.1" #socket.gethostbyname(hostname)
######################################

print("Running PO.DAAC Data Subscriber " + __version__)

# ## Before you start
#
# Before you beginning this tutorial, make sure you have an Earthdata account: [https://urs.earthdata.nasa.gov].
#
# Accounts are free to create and take just a moment to set up.
#
# ## Authentication setup
#
# The function below will allow Python scripts to log into any Earthdata Login application programmatically.  To avoid being prompted for
# credentials every time you run and also allow clients such as curl to log in, you can add the following
# to a `.netrc` (`_netrc` on Windows) file in your home directory:
#
# ```
# machine urs.earthdata.nasa.gov
#     login <your username>
#     password <your password>
# ```
#
# Make sure that this file is only readable by the current user or you will receive an error stating
# "netrc access too permissive."
#
# `$ chmod 0600 ~/.netrc`
#
# *You'll need to authenticate using the netrc method when running from command line with [`papermill`](https://papermill.readthedocs.io/en/latest/). You can log in manually by executing the cell below when running in the notebook client in your browser.*


def setup_earthdata_login_auth(endpoint):
    """
    Set up the request library so that it authenticates against the given Earthdata Login
    endpoint and is able to track cookies between requests.  This looks in the .netrc file
    first and if no credentials are found, it prompts for them.

    Valid endpoints include:
        urs.earthdata.nasa.gov - Earthdata Login production
    """
    try:
        username, _, password = netrc.netrc().authenticators(endpoint)
    except (FileNotFoundError, TypeError):
        # FileNotFound = There's no .netrc file
        # TypeError = The endpoint isn't in the netrc file, causing the above to try unpacking None
        print("There's no .netrc file or the The endpoint isn't in the netrc file")

    manager = request.HTTPPasswordMgrWithDefaultRealm()
    manager.add_password(None, endpoint, username, password)
    auth = request.HTTPBasicAuthHandler(manager)

    jar = CookieJar()
    processor = request.HTTPCookieProcessor(jar)
    opener = request.build_opener(auth, processor)
    request.install_opener(opener)

###############################################################################
# GET TOKEN FROM CMR
###############################################################################
def get_token( url: str,client_id: str, user_ip: str,endpoint: str) -> str:
    try:
        token: str = ''
        username, _, password = netrc.netrc().authenticators(endpoint)
        xml: str = """<?xml version='1.0' encoding='utf-8'?>
        <token><username>{}</username><password>{}</password><client_id>{}</client_id>
        <user_ip_address>{}</user_ip_address></token>""".format(username, password, client_id, user_ip)
        headers: Dict = {'Content-Type': 'application/xml','Accept': 'application/json'}
        resp = requests.post(url, headers=headers, data=xml)
        response_content: Dict = json.loads(resp.content)
        token = response_content['token']['id']
    except:
        print("Error getting the token - check user name and password")
    return token
###############################################################################
# DELETE TOKEN FROM CMR
###############################################################################
def delete_token(url: str, token: str) -> None:
	try:
		headers: Dict = {'Content-Type': 'application/xml','Accept': 'application/json'}
		url = '{}/{}'.format(url, token)
		resp = requests.request('DELETE', url, headers=headers)
		if resp.status_code == 204:
			print("CMR token successfully deleted")
		else:
			print("CMR token deleting failed.")
	except:
		print("Error deleting the token")
	exit(0)
###############################################################################
# Downloading the file
###############################################################################

# ## Hands-off workflow
#
# This workflow/notebook can be run routinely to maintain a time series of  data, downloading new granules as they become available at PO.DAAC.
#
# The script creates a file `.update` to the target data directory with each successful run. The file tracks to date and time of the most recent update to the time series of  granules using a timestamp in the format `yyyy-mm-ddThh:mm:ssZ`.
#
# The timestamp matches the value used for the [`created_at`](https://cmr.earthdata.nasa.gov/search/site/docs/search/api.html#g-created-at) parameter in the last successful run. This parameter finds the granules created within a range of datetimes. This workflow leverages the `created_at` parameter to search backwards in time for new granules ingested between the time of our timestamp and now.
#
# * `mins`: Initialize a new local time series by starting with the granules ingested since ___ minutes ago.
# * `shortname`: The unique Shortname  of the desired dataset.
# * `data`: The path to a local directory in which to download/maintain a copy of the NRT granule time series.


# These variables should be set before the first run, then they
#  should be left alone. All subsequent runs expect the values
#  for cmr, ccid, data to be unchanged. The mins value has no
#  impact on subsequent runs.
#

def create_parser():
    # Initialize parser
    parser = argparse.ArgumentParser()

    # Adding Required arguments
    parser.add_argument("-c", "--collection-shortname", dest="collection",required=True, help = "The collection shortname for which you want to retrieve data.")
    parser.add_argument("-d", "--data-dir", dest="outputDirectory", required=True,  help = "The directory where data products will be downloaded.")

    #Optional Arguments
    parser.add_argument("-m", "--minutes", dest="minutes", help = "How often, in minutes, should the script run (default: 60 minutes).", type=int, default=60)
    parser.add_argument("-b", "--bounds", dest="bbox", help = "The bounding rectangle to filter result in. Format is W Longitude,S Latitude,E Longitude,N Latitude without spaces. Due to an issue with parsing arguments, to use this command, please use the -b=\"-180,-90,180,90\" syntax when calling from the command line. Default: \"-180,-90,180,90\.", default="-180,-90,180,90")
    parser.add_argument("-e", "--extensions", dest="extensions", help = "The extensions of products to download. Default is [.nc, .h5]", default=[".nc", ".h5"], nargs='*')

    # Data Since: get data since a past time.
    # In this example you will get data from 2021-01-14 UTC time 00:00:00 onwards.
    # Format for the above has to be as follows "%Y-%m-%dT%H:%M:%SZ"
    parser.add_argument("-ds", "--data-since", dest="dataSince", help = "The ISO date time from which data should be retrieved. For Example, --data-since 2021-01-14T00:00:00Z", default=False)
    parser.add_argument("--version", dest="version", action="store_true",help = "Display script version information and exit.")
    return parser

from os import makedirs
from os.path import isdir, basename
from urllib.parse import urlencode
from urllib.request import urlopen, urlretrieve
from datetime import datetime, timedelta
from json import dumps, loads

if __name__ == '__main__':

    parser = create_parser()
    args = parser.parse_args()

    if args.version:
        print ("PO.DAAC Data Subscriber v" + __version__)
        exit()
    try:
        validate(args)
    except ValueError as v:
        print(v)
        exit()

    edl="urs.earthdata.nasa.gov"
    cmr="cmr.earthdata.nasa.gov"

    setup_earthdata_login_auth(edl)
    token_url="https://"+cmr+"/legacy-services/rest/tokens"
    token=get_token(token_url,'podaac-subscriber', IPAddr,edl)
    mins = args.minutes # In this case download files ingested in the last 60 minutes -- change this to whatever setting is needed
    data_since=args.dataSince
    #data_since="2021-01-14T00:00:00Z"
    #Uncomment the above line if you want data from a particular date onwards.In this example you will get data from 2021-01-14 UTC time 00:00:00 onwards.
    # Format for the above has to be as follows "%Y-%m-%dT%H:%M:%SZ"


    Short_Name=args.collection
    #This is the Short Name of the product you want to download
    # See Finding_shortname.pdf file

    ### Download Files only with the following extensions

    ## Sentinel-6 MF datasets also have *.bufr.bin, *.DBL, *.rnx, *.dat
    extensions = args.extensions

    data = args.outputDirectory
    #You should change `data` to a suitable download path on your file system.


    bounding_extent=args.bbox
    #Change this to whatever extent you need. Format is W Longitude,S Latitude,E Longitude,N Latitude



    # **The search retrieves granules ingested during the last `n` minutes.** A file in your local data dir  file that tracks updates to your data directory, if one file exists.


    timestamp = (datetime.utcnow()-timedelta(minutes=mins)).strftime("%Y-%m-%dT%H:%M:%SZ")


    # This cell will replace the timestamp above with the one read from the `.update` file in the data directory, if it exists.


    if not isdir(data):
        print("NOTE: Making new data directory at "+data+"(This is the first run.)")
        makedirs(data)
    else:
        try:
            with open(data+"/.update", "r") as f:
                timestamp = f.read()
        except FileNotFoundError:
            print("WARN: No .update in the data directory. (Is this the first run?)")
        else:
            print("NOTE: .update found in the data directory. (The last run was at "+timestamp+".)")


    # There are several ways to query for CMR updates that occured during a given timeframe. Read on in the CMR Search documentation:
    # * https://cmr.earthdata.nasa.gov/search/site/docs/search/api.html#c-with-new-granules (Collections)
    # * https://cmr.earthdata.nasa.gov/search/site/docs/search/api.html#c-with-revised-granules (Collections)
    # * https://cmr.earthdata.nasa.gov/search/site/docs/search/api.html#g-production-date (Granules)
    # * https://cmr.earthdata.nasa.gov/search/site/docs/search/api.html#g-created-at (Granules)
    # The `created_at` parameter works for our purposes. It's a granule search parameter that returns the records ingested since the input timestamp.


    if(data_since):
    	timestamp=data_since


    temporal_range=timestamp+","+datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


    params = {
        'scroll': "true",
        'page_size': 2000,
        'sort_key': "-start_date",
        'ShortName': Short_Name,
        'created_at': timestamp,
         'token': token,
        'bounding_box': bounding_extent,
    }

    if(data_since):
    	params = {
        'scroll': "true",
        'page_size': 2000,
        'sort_key': "-start_date",
        'ShortName': Short_Name,
        'temporal':temporal_range,
        'token': token,
        'bounding_box': bounding_extent ,
    	}

    # Get the query parameters as a string and then the complete search url:

    query = urlencode(params)
    url = "https://"+cmr+"/search/granules.umm_json?"+query
    print(url)


    # Get a new timestamp that represents the UTC time of the search. Then download the records in `umm_json` format for granules that match our search parameters:


    with urlopen(url) as f:
        results = loads(f.read().decode())

    print(str(results['hits'])+" new granules ingested for "+Short_Name+" since "+timestamp)

    timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


    # Neatly print the first granule record (if one was returned):

    if len(results['items'])>0:
        print(dumps(results['items'][0], indent=2))


    # The link for http access can be retrieved from each granule record's `RelatedUrls` field.
    # The download link is identified by `"Type": "GET DATA"` but there are other data files in EXTENDED METADATA" field.
    # Select the download URL for each of the granule records:


    downloads_all=[]
    downloads_data = [[u['URL'] for u in r['umm']['RelatedUrls'] if u['Type']=="GET DATA" and ('Subtype' not in u or u['Subtype'] != "OPENDAP DATA")] for r in results['items']]
    downloads_metadata = [[u['URL'] for u in r['umm']['RelatedUrls'] if u['Type']=="EXTENDED METADATA"] for r in results['items']]

    for f in downloads_data: downloads_all.append(f)
    for f in downloads_metadata: downloads_all.append(f)

    downloads = [item for sublist in downloads_all for item in sublist]

    print("Found "+str(len(downloads))+" files to download")
    # Finish by downloading the files to the data directory in a loop. Overwrite `.update` with a new timestamp on success.

    success_cnt=failure_cnt=0

    for f in downloads:
        try:
            for extension in extensions:
                if f.lower().endswith((extension)):
                    urlretrieve(f, data+"/"+basename(f))
                    print(datetime.now())
                    print("SUCCESS: "+f+"\n\n")
                    success_cnt=success_cnt+1
        except Exception as e:
            print(datetime.now())
            print("FAILURE: "+f+"\n\n")
            failure_cnt=failure_cnt+1
            print(e)
    # If there were updates to the local time series during this run and no exceptions were raised during the download loop, then overwrite the timestamp file that tracks updates to the data folder (`resources/nrt/.update`):

    if len(results['items'])>0:
    	if not failure_cnt>0:
       	 	with open(data+"/.update", "w") as f:
            		f.write(timestamp)

    print("Downloaded: "+str(success_cnt)+" files\n")
    print("Files Failed to download:"+str(failure_cnt)+"\n")
    delete_token(token_url,token)
    print("END \n\n")