#!/usr/bin/env python
# coding: utf-8

import sys
import argparse
import csv
from datetime import datetime
import xml.dom.minidom
import requests
import logging
import os
from dotenv import load_dotenv

# Initialize logging to write logs to a file and console
log_filename = "arin-roa.log"
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s"
)
file_handler = logging.FileHandler(log_filename)
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(
    logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
)
logging.getLogger().addHandler(file_handler)

# Check if running compatible python version
if sys.version_info < (3, 6, 5):
    logging.error("You need Python 3.6.5+ or later to run this script!")
    sys.exit(1)

# Get command line arguments and parse them
parser = argparse.ArgumentParser(description="Script to request ROAs via ARIN API.")
parser.add_argument("-c", "--csv", help="Specify the CSV file.", required=True)
parser.add_argument("-o", "--orgid", help="Specify the ARIN ORG-ID.", required=True)
parser.add_argument(
    "-p",
    "--production",
    action="store_true",
    help="Use production API.",
    required=False,
)
parser.add_argument(
    "--debug", action="store_true", help="Enable debug mode.", required=False
)
args = parser.parse_args()

# Take environment variables from .env file
load_dotenv()
args.apikey = os.getenv("ARIN_API_KEY")

nowDate = datetime.now().strftime("%Y%m%d")

if not args.apikey:
    logging.error(
        "Please set ARIN_API_KEY as an environment variable or store it in .env file."
    )
    sys.exit(1)

# Triple check if user really wants to use production API
if args.production:
    logging.info(
        'To execute this on the Production API, type "production". Otherwise, the application will exit.'
    )
    prod = input().strip().lower()

    if prod != "production":
        sys.exit(1)

    logging.info('Please confirm by typing "yes".')
    yes_really_prod = input().strip().lower()

    if yes_really_prod != "yes":
        sys.exit(1)


# Function to generate the roaData
def generate_roaData(asn: str, prefix: str, mask: str, maxLength: str) -> str:
    name = f'AS{asn}-NET-{prefix.replace("::", "-").replace(":", "-").replace(".", "-")}-{mask}-{maxLength}-{nowDate}'
    roaSpec = f"""
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
        </roaSpec>"""
    return roaSpec


# Function to perform the POST to the ARIN API
def roa_request(roaData: str) -> str:
    """
    Post the ROA object to ARIN API
    https://www.arin.net/resources/manage/regrws/payloads/#rpki-transaction-payload
    https://www.arin.net/resources/manage/regrws/methods/#route-origin-authorizations-roas
    https://www.arin.net/reference/tools/testing/#using-reg-rws-and-the-irr-restful-api-in-ot-e
    https://www.arin.net/reference/tools/testing/#using-rpki-in-arin-s-ot-e-environment
    """
    # Set API baseurl based off production or not
    base_url = "reg.arin.net" if args.production else "reg.ote.arin.net"

    payload = f"""<rpkiTransaction xmlns="http://www.arin.net/regrws/rpki/v1">
                    <roaSpecAdd>{roaData}</roaSpecAdd>
                </rpkiTransaction>"""

    # Construct the headers
    headers = {"Content-Type": "application/xml", "Accept": "application/xml"}

    # Construct the URL
    url = f"https://{base_url}/rest/rpki/{args.orgid}?apikey={args.apikey}"

    if args.debug:
        logging.debug(f"URL: {url}")
        logging.debug(f"Headers: {headers}")
        logging.debug(f"Payload: {payload}")

    # POST to API or error out
    try:
        # Make API call and get response
        response = requests.post(url, data=payload, headers=headers)
        response.raise_for_status()
    # Handle errors
    except requests.exceptions.RequestException as e:
        logging.error(f"Request failed: {e}")
        sys.exit(1)

    # Parse response
    dom = xml.dom.minidom.parseString(response.content.decode("utf-8"))
    response_content = dom.toprettyxml()

    # Check response status and handle errors
    if response.status_code == 200:
        logging.info(f"ROA successfully created: {roaData}")
    else:
        dom = xml.dom.minidom.parseString(response.content.decode("utf-8"))
        errors = dom.getElementsByTagName("message")
        for error in errors:
            logging.error(
                f"Error creating ROA: {roaData}, Message: {error.firstChild.nodeValue}"
            )
    # Log result
    logging.debug(f"Response: {response_content}")
    return response


# Read and process the CSV file
with open(args.csv) as csvfile:
    readCSV = csv.reader(csvfile, delimiter=",")
    with open(log_filename, "a") as log:
        for row in readCSV:
            asn, prefix, mask, maxLength = row
            body = generate_roaData(asn, prefix, mask, maxLength)
            response_payload = roa_request(body)
