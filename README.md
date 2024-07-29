# ARIN ROA Request and List/Deletion Scripts

Three scripts to connect to ARIN's OT&E and Production RESTful APIs.  One script is to create ROAs in the old API which needed the ROAs to be signed by the private key (`arin-roa-request.py`) , one script which uses the new API (as of 2/23) which generates auto-renewing ROAs (`create_arin_rpki_roas.py`) and one is to list/delete them (`arin-delete-roas.py`).

## Table of Contents

- [ARIN ROA Request and List/Deletion Scripts](#arin-roa-request-and-listdeletion-scripts)
  - [Table of Contents](#table-of-contents)
  - [New RPKI ROA creation](#new-rpki-roa-creation)
  - [Legacy RPKI ROA creation](#legacy-rpki-roa-creation)
  - [Importance of RPKI and ROAs](#importance-of-rpki-and-roas)

**Note! The scripts `arin-roa-request.py`, `create_arin_rpki_roas.py`, and `arin-delete-roas.py` by default only make an API call to ARIN's OT&E (Operational Test & Evaluation) Environment.  Any change made in the OT&E is just a test and does not impact the "real" environment.  If you want to make an API call to ARIN's production API, specify the -p/--production command line argument.**

To install necessary python modules please run:

`pip install requirements.txt`

**Note, the maxLength is required in this script!  It is recommended that the maxLength be equal to the CIDR mask.  If you set the maxLength too large (ex. /24 or /48) you open yourself up to a potential forged-origin subprefix hijack (see this IETF doc: <https://tools.ietf.org/html/draft-ietf-sidrops-rpkimaxlen>)**

## New RPKI ROA creation

"To receive the benefit of auto-renewing ROAs, please use the new endpoint to Create and Delete ROAs. The new endpoint is both simpler and more powerful." - ARIN

[LINK](https://www.arin.net/resources/manage/regrws/methods/#create-and-delete-roas) TO ARIN API Documents.

The new ROA creation script `create_arin_rpki_roas.py` needs to have a CSV file specified which defines the values for each ROA that is created.  The format of the CSV is:
Origin AS,IP prefix,CIDR mask,maxLength
Ex:

```csv
65000,192.0.2.0,24,24
```

The new ROA create script can be run like this for OT&E:

`./create_arin_rpki_roas.py -c example-roa.csv -o <ORG-ID>`

The new ROA create script can be run like this for production (note -p command line argument specified for production):

`./create_arin_rpki_roas.py -c example-roa.csv -o <ORG-ID> -p`

## Legacy RPKI ROA creation

In order to execute the scripts you will need to generate an API key.  The `create_arin_rpki_roas.py` script needs an API key generated after 2/23.  See this link to find out more info on generating an API key with ARIN: <https://www.arin.net/reference/materials/security/api_keys/>

To create ROAs on the old API you will also need a private key that will be used to sign your ROAs.  The OT&E has a special private key that is used for signing all ROAs in that test environment.  The test private key can be downloaded here: <https://www.arin.net/reference/tools/testing/ote_roa_req_signing_key.private.pem>
More info is here: <https://www.arin.net/reference/tools/testing/#roa-request-generation-key-pairs>
The new API does not require a private key and auto-renews the ROAs!

For production, you will need to generate your own public/private key pair to create ROAs or use the new API and the `create_arin_rpki_roas.py` script.  This procedure is documented at <https://www.arin.net/resources/manage/rpki/roa_request/>

Here’s the procedure to generate a public/private keypair:

This command generates a ROA Request Generation Key Pair and saves it as a file named org_privkey.pem:

`openssl genrsa -out org_privkey.pem 2048`

This command extracts the public key from the org_privkey.pem and writes it to a file named `org_pubkey.pem`:

`openssl rsa -in org_privkey.pem -pubout -outform PEM -out org_pubkey.pem`

For ARIN, the contents of the `org_pubkey.pem` needs to be uploaded to "Public Key" section of the Managing RPKI page of the ORG-ID.  See <https://www.arin.net/resources/manage/rpki/hosted/#cert-request>

Keep the `org_privkey.pem` file private, perhaps in an HSM.  If the security of the private key is compromised, you should delete all of the ROAs created with that key and generate a new key pair and new ROAs.

The old ROA creation script needs to have a CSV file specified which defines the values for each ROA that is created.  The format of the CSV is:
Origin AS,IP prefix,CIDR mask,maxLength
Ex: `65000,192.0.2.0,24,24`

The old ROA creation script can be run like this for OT&E:

`./arin-roa-request.py -c ROAs.txt -a <ARIN API KEY> -k ote_roa_req_signing_key.private.pem -o <ORG-ID> --debug`

The old ROA creation script can be run like this for production (note -p command line argument specified for production):

`./arin-roa-request.py -c ROAs.txt -a <ARIN API KEY> -k orgkeypair.pem -o <ORG-ID> --debug -p`

The ROA deletion script can be run like this to output a CSV list of existing ROAs in OT&E and put the CSV into a file:

`./arin-delete-roas.py -l  -a <ARIN API KEY> -o <ORG-ID> > ROAs-to-be-deleted.csv`

You can now edit the `ROAs-to-be-deleted.csv` file and remove the ROAs that you don't want to be deleted.

The ROA deletion script can be run like this to delete a CSV list of existing ROAs (use output from list command above) in OT&E:

`./delete-roas.py -f <CSV file of ROAs to delete> -o <ORG-ID> -a <ARIN API KEY>`

## Importance of RPKI and ROAs

**And remember, when you create ROAs for your prefixes you are protecting those prefixes against BGP origin hijacks.  When you perform ROV (<https://tools.ietf.org/html/rfc6811>) on your eBGP routers, you are helping to protect others from BGP origin hijacks.  It only takes one ASN in the AS path to perform ROV for protection against BGP origin hijacks. The more networks that implement these technologies, the safer we all are!**

Please check out <https://docs.google.com/document/d/1fGsuDpLSn0ZN3-Pa-4aAciGH-Qc0K5AHZ1GyFRAHow4/edit?usp=sharing> for more info on implementing RPKI in your network!
