from botocore.vendored import requests
import validatesns
import json

certs = {}

def get_certificate(url):
    if url not in certs:
        r = requests.get(url)
        r.raise_for_status()
        certs[url] = r.content

    return certs[url]

def lambda_handler(event, context):
    validatesns.validate(event, get_certificate=get_certificate)

    if event['Type'] == 'SubscriptionConfirmation':
        r = requests.get(event['SubscribeURL'])
        r.raise_for_status()
        r.close()
        print "Subscription confirmed"
        return

    # Todo: actually handle notification

    print json.dumps(event, indent=4)
