#!/usr/bin/env python
# coding: utf-8


import sys
import argparse
import base64
import csv
import time
from datetime import datetime, date
#from datetime import datetime,timedelta
from bs4 import BeautifulSoup
import xml.dom.minidom
import requests
from logger import myLogger
from bs4 import BeautifulSoup


if sys.version_info<(3,6,5):
    sys.stderr.write('You need python 3.6.5+ or later to run this script!\n')
    sys.exit(1)


# Get command line arguments and parse them
parser = argparse.ArgumentParser(description='This is a script that reads in a CSV and makes API calls to ARIN to request ROAs.')
parser.add_argument('-c','--csv', help='Specify a CSV with each line in the format: Origin AS,AS name,IP prefix,CIDR mask,maxLength.  Ex: 65000,Florida_Market,192.0.2.0,24,24',required=True)
parser.add_argument('-a','--apikey', help='Specify the ARIN API key.',required=False)
parser.add_argument('-o','--orgid', help='Specify the ARIN ORG-ID associated with the prefixes.',required=True)
parser.add_argument('-p','--production', action='store_true', help='Specify that you want to execute the API call in production and not OT&E.',required=False)
parser.add_argument('--debug', action='store_true', help='Enable debug mode',required=False)


# Parse all the arguments
args = parser.parse_args()

nowDate = datetime.now().strftime('%Y%m%d')

if not args.apikey:
    try:
       with open('apikey.txt') as key:
          args.apikey = key.read()[:-1]
    except:
       myLogger.debug('Cannot open apikey.txt. please use -a')
       print('Cannot open apikey.txt. please use -a')
       exit()


# Does the user want to execute this on the production API?
if args.production:
    print ('If you want to execute this on the Production API, please type \'production\'. Otherwise the application will exit.')
    prod = str(input())

    if prod.lower() == 'production':
        print('\nOK, just checking one more time that you REALLY want to execute this on the production API.  If so, type \'Yes\'. Otherwise the application will exit.')
        yes_really_prod = str(input())
        if yes_really_prod.lower() != 'yes':
            exit()
    else:
        exit()



# Define a function to generate the roaData
def generate_roaData(asn: str, asn_name: str, prefix: str, mask: str, maxLengh: str) -> str:
    # add roaSpec
    if asn_name:
        name = asn_name.replace('::', '-').replace(':','-').replace('.','-')
    else:
        name = 'AS' + asn + '-NET-' + prefix.replace('::', '-').replace(':','-').replace('.','-') + '-' + mask + '-' + maxLengh + '-' + nowDate
    roaSpec = f'''
        <roaSpec> 
            <asNumber>{asn}</asNumber> 
            <name>{name}</name> 
                <resources> 
                    <roaSpecResource> 
                        <startAddress>{prefix}</startAddress> 
                        <cidrLength>{mask}</cidrLength>
                        <maxLength>{maxLength}</maxLength>
                    </roaSpecResource> 
                </resources> 
        </roaSpec>'''
        
    return roaSpec


# Perform the POST to the ARIN API to request the ROA and get the return code
def roa_request(roaData: str, log) -> str:
    '''
    Builds the ARIN ROA object per API details
    https://www.arin.net/resources/manage/regrws/payloads/#rpki-transaction-payload
    https://www.arin.net/resources/manage/regrws/methods/#route-origin-authorizations-roas
    https://www.arin.net/reference/tools/testing/#using-reg-rws-and-the-irr-restful-api-in-ot-e
    https://www.arin.net/reference/tools/testing/#using-rpki-in-arin-s-ot-e-environment
    '''
    # Make API call to either prod or OT&E
    if 'yes_really_prod' in globals():
        if yes_really_prod.lower() == 'yes':
            host = 'reg.arin.net'
    else:
        host = 'reg.ote.arin.net'

    # Construct the XML data
    payload = f'''<rpkiTransaction xmlns="http://www.arin.net/regrws/rpki/v1">
                    <roaSpecAdd>{roaData}</roaSpecAdd>
                </rpkiTransaction>'''
    # Construct the headers
    headers = {'Content-Type': 'application/xml', 'Accept': 'application/xml'}
    # Construct the URL
    url = f'https://{host}/rest/rpki/{args.orgid}?apikey={args.apikey}'
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
        myLogger.debug('Uh oh we got an http error!')
        if args.debug:
            print('Uh oh we got an http error!')
        raise SystemExit(e)
    except requests.exceptions as e:
        myLogger.debug('Uh oh we got a requests error!')
        if args.debug:
            print('Uh oh we got a requests error!')
        raise SystemExit(e)
    except Exception as e:
        myLogger.debug('Uh oh something wrong. error!')
###     ERROR

    dom = xml.dom.minidom.parseString(response.content.decode('utf-8'))
    response_content = dom.toprettyxml()

    # Check to see if the response was 200.  If so, everything is ok.  Else print error response
    if str(response) == "<Response [200]>":
        log.write(f'ROA successfully created for ROA: {roaData}\n')
        print(f'ROA successfully created for ROA: {roaData}')
    else:
        bs_data = BeautifulSoup(response.content.decode('utf-8'), 'xml')
        for idx,data in enumerate(bs_data.find_all('component')):
            message = data.find('message').text
            log.write(f'ERROR! ROA creation failed for ROA: {roaData}! {message}\n')
            print(f'ERROR! ROA creation failed for ROA: {roaData}! {message}')


    #Print debug
    myLogger.debug(f'Response is:\n{response_content}')
    if args.debug:
        print(f'Response is:\n{response_content}')

    return response  


# Open the csv file and read each line
with open(args.csv) as csvfile:
    # log file
    now = time.strftime('%m-%d_%H')
    logName = '/tmp/RPKI/log/' + now + '_arin-roa-request.log'
    readCSV = csv.reader(csvfile, delimiter=',')

    with open(logName, "w+") as log:
      for row in readCSV:
        # Set the various rows to the variables we need
        body=''
        asn = row[0]
        asn_name = row[1]
        prefix = row[2]
        mask = row[3]
        maxLength = row[4]
        body = generate_roaData(asn, asn_name, prefix, mask, maxLength)
      #roaData_payload = createXml(body)
      #response_payload = roa_request(roaData_payload, log)
        response_payload = roa_request(body, log)

