# ARIN ROA Request
Two scripts to connect to ARIN's OT&E and Production RESTful APIs.  One script is to create ROAs and the other is to list/delete them.

**Note! The scripts arin-roa-request.py and arin-delete-roas.py by default only make an API call to ARIN's OT&E (Operational Test & Evaluation) Environment.  Any change made in the OT&E is just a test and does not impact the "real" environment.  If you want to make an API call to ARIN's production API, specify the -p/--production command line argument.**

In order to execute the script you will need to generate an API key.  See this link to find out more info on generating an API key with ARIN: https://www.arin.net/reference/materials/security/api_keys/

You will also need a private key that will be used to sign your ROAs.  The OT&E has a special private key that is used for signing all ROAs in that test environment.  The test private key can be downloaded here: https://www.arin.net/reference/tools/testing/ote_roa_req_signing_key.private.pem 
More info is here: https://www.arin.net/reference/tools/testing/#roa-request-generation-key-pairs

For production, you will need to generate your own public/private key pair.  This procedure is documented at https://www.arin.net/resources/manage/rpki/roa_request/
Here’s the procedure to quickly create a ROA in ARIN using your browser:
Create your public/private key pair using OpenSSL:
```openssl genrsa -out org keypair.pem 2048```
This command generates a ROA Request Generation Key Pair and saves it as a file named orgkeypair.pem.
```openssl rsa -in orgkeypair.pem -pubout -outform PEM -out org_pubkey.pem```
This command extracts the public key from the ROA Request Generation key pair and writes it to a file named ```org_pubkey.pem```.
Keep the ```orgkeypair.pem``` file private, perhaps in an HSM.  If the security of the private key is compromised, you should delete all of the ROAs created with that key and generate a new key pair and new ROAs.

The script needs to have a CSV file specified which defines the values for each ROA that is created.  The format of the CSV is:
Origin AS,IP prefix,CIDR mask,maxLength
Ex: ```65000,192.0.2.0,24,24```
**Note, the maxLength is required in this script!  It is recommended that the maxLength be equal to the CIDR mask.  If you set the maxLength too large (ex. /24 or /48) you open yourself up to a potential forged-origin subprefix hijack (see this IETF doc: https://tools.ietf.org/html/draft-ietf-sidrops-rpkimaxlen)**

The ROA creation script can be run like this for OT&E:
```./arin-roa-request.py -c ROAs.txt -a <ARIN API KEY> -k ote_roa_req_signing_key.private.pem -o <ORG-ID> --debug```

The ROA creation script can be run like this for production:
```./arin-roa-request.py -c ROAs.txt  -k org_pubkey.pem -o <ORG-ID> -p```

The ROA deletion script can be run like this to output a CSV list of existing ROAs in OT&E:
```./arin-delete-roas.py -l -o <ORG-ID> -a <ARIN API KEY>```

The ROA deletion script can be run like this to delete a CSV list of existing ROAs (use output from list command above) in OT&E:
```./delete-roas.py -f <CSV file of ROAs to delete> -o <ORG-ID> -a <ARIN API KEY>```

Again, if you want to execute the two above commands on the production API, use the ```-p``` switch.

