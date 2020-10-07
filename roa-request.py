#!/usr/bin/python3

# Written by Rich Compton rich.compton@charter.com
# This is a script that reads in a CSV with each line as
# Origin AS,IP prefix,CIDR mask,maxLength
# Ex: 65000,192.0.2.0,24,24
# For each line it will make an API call to ARIN to request a ROA be created

import sys
import requests
import argparse
import OpenSSL
from OpenSSL import crypto
import base64
import csv
import time
import xml.dom.minidom

# Check to see if we are running in python 3, exit if not
if sys.version_info<(3,0,0):
   sys.stderr.write('You need python 3.0+ or later to run this script!\n')
   exit(1)

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
def generate_roaData(asn, prefix, mask, maxLength):
    # Define the global variable roaData
    global roaData
    # Replace all IPv6 double colons with a single dash
    name = prefix.replace('::', '-')
    # Replace all IPv6 single colons with a dash
    name = name.replace(':', '-')
    # Replace all IPv4 dots with dashes
    name = name.replace('.', '-')
    # Generate the name 
    name = 'AS'+asn+'-NET-'+name+'-'+mask
    # Get the epoch time in seconds (remove miliseconds)
    epoch_time = int(time.time()) 
    # Get the date today
    today =(time.strftime('%m-%d-%Y')) 
    # Get the current year
    this_year = (time.strftime('%Y')) 
    # Get the current month and day
    this_day_month = (time.strftime('%m-%d-'))
    # Add 10 years to the current year
    # !!!!The OT&E CA has a cert that expires in 9 years!!!!
    # !!!!Change this back to 10 for prod!!!!
    ten_years = int(this_year)+8
    # Construct the date in 10 years
    datePlusTenYears = this_day_month+str(ten_years)
    # Generate the roaData
    roaData = '1|'+str(epoch_time)+'|'+name+'|'+asn+'|'+today+'|'+datePlusTenYears+'|'+prefix+'|'+mask+'|'+maxLength+'|'
    if args.debug:
        print('roaData is:\n',roaData,'\n')
    return roaData


# This function generates the signature of the roaData using the private key
def generate_signature(roaData):
    # Define the global variable signature
    global signature
    # Open the PEM private key file
    key_file = open(args.key, 'r') 
    # Read in the key from the file
    key = key_file.read()
    # Close the opened file
    key_file.close()
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
def roa_request(signature, roaData):
    # Define the global variable response
    global response
    # Resource Classification is ARIN
    resource_class = 'AR'
    # Construct the XML data
    payload = """<roa xmlns="http://www.arin.net/regrws/rpki/v1">
                    <signature>%s</signature>
                    <roaData>%s</roaData>
                </roa>""" % (signature.decode('utf-8') , roaData)
    # Construct the headers
    headers = {'Content-Type': 'application/xml', 'Accept': 'application/xml'}
    # Construct the URL
    # !!!! Change to REAL URL for Prod !!!!
    url = 'https://reg.ote.arin.net/rest/roa/'+args.orgid+';resourceClass='+resource_class+'?apikey='+args.apikey
    if args.debug:
        print('The URL to POST to is:\n',url,'\n')
        print('The headers to POST are:\n', headers)
        print('The payload to post is:\n', payload)
    
    # Attempt to make post to API or error out
    try:
        # Make API call and get response
        response = requests.post(url, data=payload, headers=headers)
    # Handle errors 
    except requests.exceptions.HTTPError as e:
        if args.debug:
            print('Uh oh we got an http error!\n')
        print (e)
        sys.exit(1)
    except requests.exceptions as e:
        if args.debug:
            print('Uh oh we got a requests error!\n')
            print (e)
            sys.exit(1)
    if args.debug:
            dom = xml.dom.minidom.parseString(response.content.decode('utf-8'))
            pretty_xml_as_string = dom.toprettyxml()
            print('Response is:\n',pretty_xml_as_string)
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
        # Call function to generate the roaData string
        generate_roaData(asn, prefix, mask, maxLength)
        # Call function to generate the signature of the roaData string
        generate_signature(roaData)
        # Call function to make API POST to ARIN's site
        roa_request(signature, roaData)
        print('For prefix: '+prefix+' the response from the API was:'+str(response))
