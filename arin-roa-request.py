#!/usr/bin/python3

'''
This is a script that reads in a CSV with each line as
Origin AS,IP prefix,CIDR mask,maxLength
Ex: 65000,192.0.2.0,24,24
For each line it will make an API call to ARIN to request a ROA be created
'''

import sys
import argparse
import base64
import csv
import xml.dom.minidom
import OpenSSL
from datetime import datetime,timedelta
from OpenSSL import crypto
import requests

# Check to see if we are running in python 3, exit if not
if sys.version_info<(3,6,5):
    sys.stderr.write('You need python 3.6.5+ or later to run this script!\n')
    sys.exit(1)

# Get command line arguments and parse them
parser = argparse.ArgumentParser(description='This is a script that reads in a CSV and makes API calls to ARIN to request ROAs.')
parser.add_argument('-c','--csv', help='Specify a CSV with each line in the format: Origin AS,IP prefix,CIDR mask,maxLength.  Ex: 65000,192.0.2.0,24,24',required=True)
parser.add_argument('-a','--apikey', help='Specify the ARIN API key.',required=True)
parser.add_argument('-k','--key', help='Specify the location of the ORG-ID PEM private key file used for signing ROAs.',required=True)
parser.add_argument('-o','--orgid', help='Specify the ARIN ORG-ID associated with the prefixes.',required=True)
parser.add_argument('--debug', action='store_true', help='Enable debug mode',required=False)

# Parse all the arguments
args = parser.parse_args()

# Define a function to generate the roaData
def generate_roaData(asn: str, prefix: str, mask: str, max_length: str) -> str:
    '''
    Takes values from CSV and returns back the ROA object payload
    '''
    # Replace all IPv6 double colons with a single dash
    name = prefix.replace('::', '-')
    # Replace all IPv6 single colons with a dash
    name = name.replace(':', '-')
    # Replace all IPv4 dots with dashes
    name = name.replace('.', '-')
    # Generate the name
    name = f'AS{asn}-NET-{name}-{mask}'
    create = datetime.now()
    epoch_time = int(create.timestamp())
    # Set expire time to 520 weeks from today's date (520 weeks)
    expire = create + timedelta(weeks=520)
    creation = f'{create.day}-{create.month}-{create.year}'
    expiration = f'{expire.month}-{expire.day}-{expire.year}'
    # Generate the roaData
    roaData = f'1|{epoch_time}|{name}|{asn}|{creation}|{expiration}|{prefix}|{mask}|{max_length}|'
    if args.debug:
        print('roaData is:\n',roaData,'\n')
    return roaData


# This function generates the signature of the roaData using the private key
def generate_signature(roaData: str) -> str:
    '''
    From the ROA object created a signature is computed and returned
    '''
    # Open the PEM private key file
    with open(args.key,) as key_file:
        key = key_file.read()
    # Load in the private key to an object
    pkey = crypto.load_privatekey(crypto.FILETYPE_PEM, key)
    # encode the roaData in utf8
    roaData = roaData.encode('utf8')
    # Sign the roaData
    sign = OpenSSL.crypto.sign(pkey, roaData, 'sha256')
    # Encode the signature in base64
    signature = base64.b64encode(sign)
    # Return the signature
    if args.debug:
        print('The signature generated is:\n',signature.decode('utf-8'),'\n')
    return signature

# Perform the POST to the ARIN API to request the ROA and get the return code
def roa_request(signature: str, roaData: str) -> str:
    '''
    Builds the ARIN ROA object per API details
    '''
    # Resource Classification is ARIN
    resource_class = 'AR'
    signature = signature.decode('utf-8')
    # Construct the XML data
    payload = f'''<roa xmlns="http://www.arin.net/regrws/rpki/v1">
                    <signature>{signature}</signature>
                    <roaData>{roaData}</roaData>
                </roa>'''
    # Construct the headers
    headers = {'Content-Type': 'application/xml', 'Accept': 'application/xml'}
    # Construct the URL
    # !!!! Change to REAL URL for Prod !!!!
    url = f'https://reg.arin.net/rest/roa/{args.orgid};resourceClass={resource_class}?apikey={args.apikey}'
    if args.debug:
        print(f'The URL to POST to is:\n{url}')
        print(f'The headers to POST are:\n{headers}')
        print(f'The payload to post is:\n{payload}')

    # Attempt to make post to API or error out
    try:
        # Make API call and get response
        response = requests.post(url, data=payload, headers=headers)
    # Handle errors
    except requests.exceptions.HTTPError as e:
        if args.debug:
            print('Uh oh we got an http error!')
        raise SystemExit(e)
    except requests.exceptions as e:
        if args.debug:
            print('Uh oh we got a requests error!')
        raise SystemExit(e)
    if args.debug:
        dom = xml.dom.minidom.parseString(response.content.decode('utf-8'))
        pretty_xml_as_string = dom.toprettyxml()
        print(f'Response is:\n{pretty_xml_as_string}')
    return response

# Open the csv file and read each line
with open(args.csv) as csvfile:
    readCSV = csv.reader(csvfile, delimiter=',')
    for row in readCSV:
        # Set the various rows to the variables we need
        asn = row[0]
        prefix = row[1]
        mask = row[2]
        maxLength = row[3]
        roaData_payload = generate_roaData(asn, prefix, mask, maxLength)
        signature_payload = generate_signature(roaData_payload)
        response_payload = roa_request(signature_payload, roaData_payload)
        print(f'For prefix:{prefix} the response from the API was:{response_payload}')
