#!/usr/bin/python3

'''
Written by Rich Compton rich.compton@charter.com
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
parser.add_argument('-e','--expiration', help='Specify the number of weeks out to set the certificate expiration.  If unset, it will default to 312 weeks (6 years) for production or 4 weeks for OT&E.',required=False)
parser.add_argument('-k','--key', help='Specify the location of the ORG-ID PEM private key file used for signing ROAs.',required=True)
parser.add_argument('-o','--orgid', help='Specify the ARIN ORG-ID associated with the prefixes.',required=True)
parser.add_argument('-p','--production', action='store_true', help='Specify that you want to execute the API call in production and not OT&E.',required=False)
parser.add_argument('--debug', action='store_true', help='Enable debug mode',required=False)

# Parse all the arguments
args = parser.parse_args()

# Does the user want to execute this on the production API?
if args.production:
    print ('If you want to execute this on the Production API, please type \'production\'.  If you don\'t type this, then the API calls will be made to the OT&E API.')
    prod = str(input()) 

    if prod == 'production':
        print('OK, just checking one more time that you really, really, REALLY want to execute this on the production API.  If so, type \'Yes\'.')
        yes_really_prod = str(input()) 
        if yes_really_prod != 'production':
            print("You didn't type \'Yes\' so I'm quitting.  FYI, this is case sensitive.  You must type \'Yes\' to execute in production!")
            quit()

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
    # Change to 6 years (312 weeks) or whatever specified for prod by default or 4 weeks for OT&E 
    if 'yes_really_prod' in globals():
        if yes_really_prod == 'Yes':
            if args.expiration:
                expire_weeks = int(args.expiration)
            else:
                expire_weeks = 312
    else:
         if args.expiration:
             if int(args.expiration) > 4:
                 sys.stderr.write('For OT&E, the expiration value can\'t be greater than 4 weeks. \n')
                 sys.exit(1)
             expire_weeks = int(args.expiration)
         else:
             expire_weeks = 4
    expire = create + timedelta(weeks=expire_weeks)
    creation = f'{create.month}-{create.day}-{create.year}'
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
    #sign = OpenSSL.crypto.sign(pkey, roaData, 'sha256')
    sign = crypto.sign(pkey, roaData, 'sha256')
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
    # Make API call to either prod or OT&E
    if 'yes_really_prod' in globals():
        if yes_really_prod == 'Yes':
            host = 'reg.arin.net'
    else:
        host = 'reg.ote.arin.net'
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
    url = f'https://{host}/rest/roa/{args.orgid};resourceClass={resource_class}?apikey={args.apikey}'
    if args.debug:
        print(f'The URL to POST to is:\n{url}')
        print(f'The headers to POST are:\n{headers}')
        print(f'The payload to post is:\n{payload}')

    # POST to API or error out
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
    dom = xml.dom.minidom.parseString(response.content.decode('utf-8'))
    response_content = dom.toprettyxml()
   
    # Check to see if the response was 200.  If so, everything is ok.  Else print error response
    if str(response) == "<Response [200]>": 
        print(f'ROA successfully created for ROA: {roaData}')
    else:
        print(f'ERROR! ROA creation failed for ROA: {roaData}!')
    
    #Print debug
    if args.debug:
        print(f'Response is:\n{response_content}')

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
