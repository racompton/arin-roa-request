#!/usr/bin/python3

'''
Written by Rich Compton rich.compton@charter.com
This is a script that will do two functions.  
-first it will list the roaHandle and IP Prefix for each ROA in an ORG-ID
-second it will delete the ROAs defined by the roaHandle in a txt file
'''

import sys
import argparse
import requests
import csv
import xml.dom.minidom
from bs4 import BeautifulSoup

# Check to see if we are running in python 3, exit if not
if sys.version_info<(3,6,5):
    sys.stderr.write('You need python 3.6.5+ or later to run this script!\n')
    sys.exit(1)

# Get command line arguments and parse them
parser = argparse.ArgumentParser(description='This is a script that will do two functions: \nFirst it will list the roaHandle and IP Prefix for each ROA in an ORG-ID. \n Second it will delete the ROAs defined by the roaHandle in a txt file.')
parser.add_argument('-l','--list', action='store_true', help='List the roaHandle, ASN, IP prefix, and mask for each ROA in an ORG-ID.',required=False)
parser.add_argument('-f','--file', help='Specify the text file that has a list of roaHandles to be deleted.',required=False)
parser.add_argument('-a','--apikey', help='Specify the ARIN API key.',required=True)
parser.add_argument('-o','--orgid', help='Specify the ARIN ORG-ID associated with the prefixes.',required=False)
parser.add_argument('-p','--production', action='store_true', help='Specify that you want to execute the API call in production and not OT&E.',required=False)
parser.add_argument('--debug', action='store_true', help='Enable debug mode',required=False)

# Parse all the arguments
args = parser.parse_args()

orgid = args.orgid
apikey = args.apikey
file = args.file

if args.production:
    # Does the user want to execute this on the production API?
    print ('If you want to execute this on the Production API, please type \'production\'.  If you don\'t type this, then the API calls will be made to the OT&E API.')
    prod = str(input()) 

    if prod == 'production':
        print('OK, just checking one more time that you really, really, REALLY want to execute this on the production API.  If so, type \'Yes\'.')
        yes_really_prod = str(input()) 

def list_roas(orgid, apikey):
    '''
    Takes in the ORG-ID and API Key and returns the list of roaHandles created 
    '''
    if 'yes_really_prod' in globals():
        if yes_really_prod == 'Yes':
            host = 'reg.arin.net'
    else:
        host = 'reg.ote.arin.net'
    url = f'https://{host}/rest/roa/{args.orgid}?apikey={args.apikey}'
    if args.debug:
        print(f'The URL to GET is:\n{url}')
    try:
        # Make API call and get response
        response = requests.get(url)
    # Handle errors
    except requests.exceptions.HTTPError as e:
        if args.debug:
            print('Uh oh we got an http error!')
        raise SystemExit(e)
    except requests.exceptions as e:
        if args.debug:
            print('Uh oh we got a requests error!')
        raise SystemExit(e)
    bs_data = BeautifulSoup(response.content.decode('utf-8'), 'xml')
    for idx,data in enumerate(bs_data.find_all('roaSpec')):
        roa_handle = data.find('roaHandle')
        roa_asn = data.find('ns5:asNumber')
        for resource in data.find_all('resources'):
            start_address = resource.find('ns5:startAddress')
            cidr_length = resource.find('ns5:cidrLength')
            print(f'{roa_handle.text},{roa_asn.text},{start_address.text},{cidr_length.text}')
    return response

def delete_roas(file, apikey):
    '''
    Takes in the file to delete and the API Key and deletes each roaHandle in the file
    '''
    with open(file) as delete_list:
        readCSV = csv.reader(delete_list, delimiter=',')
        for row in readCSV:
            roaHandle = row[0]
            if 'yes_really_prod' in globals():
                if yes_really_prod == 'Yes':
                    host = 'reg.arin.net'
            else:
                host = 'reg.ote.arin.net'
            url = f'https://{host}/rest/roa/spec/{roaHandle}?apikey={apikey}'
            if args.debug:
                print(f'The URL to DELETE is:\n{url}')
            try:
                # Make API call and get response
                response = requests.delete(url)
            # Handle errors
            except requests.exceptions.HTTPError as e:
                if args.debug:
                    print('Uh oh we got an http error!')
                raise SystemExit(e)
            except requests.exceptions as e:
                if args.debug:
                    print('Uh oh we got a requests error!')
                raise SystemExit(e)
            dom = xml.dom.minidom.parseString(response.content.decode('utf-8'))
            response_content = dom.toprettyxml()
            if str(response) == "<Response [200]>": 
                print(f'Successfully deleted ROA with roaHandle: {roaHandle}')
            else:
                print(f'ERROR! ROA deletion failed for ROA with roaHandle:{roaHandle}!')
            if args.debug:
                print(f'The response from the server for the deletion of {roaHandle} is:\n{response_content}')


if args.list:
    response_payload = list_roas(args.orgid, args.apikey)
    if args.debug:
        dom = xml.dom.minidom.parseString(response_payload.content.decode('utf-8'))
        pretty_xml_as_string = dom.toprettyxml()
        print(f'Here are the ROAs for {args.orgid}:\n{pretty_xml_as_string}')
    
if args.file:
    response_payload = delete_roas(args.file, args.apikey)
