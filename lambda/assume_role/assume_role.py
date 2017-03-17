import base64
import boto3
import os

kms = boto3.client('kms')
sts = boto3.client('sts')

KMS_KEY_ID = os.environ['KMS_KEY_ID']

def encrypt(plaintext):
    return base64.b64encode(kms.encrypt(
        KeyId=KMS_KEY_ID, Plaintext=plaintext)['CiphertextBlob'])

def lambda_handler(event, context):
    resp = sts.assume_role(
        RoleArn=event['RoleARN'],
        RoleSessionName=event['ExecutionName'])

    secret_access_key_ciphertext = encrypt(resp['Credentials']['SecretAccessKey'])

    # Not encrypting the session token here because 1) not sure it's
    # necessary and 2) STS doesn't make a commitment that it will
    # always be less than 4K:
    #
    #     Note: The size of the security token that STS APIs return is
    #     not fixed. We strongly recommend that you make no
    #     assumptions about the maximum size. As of this writing, the
    #     typical size is less than 4096 bytes, but that can
    #     vary. Also, future updates to AWS might require larger
    #     sizes.
    #
    # Should double-check with IAM to make sure this is kosher.

    return {
        'AccessKeyId': resp['Credentials']['AccessKeyId'],
        'SecretAccessKeyCiphertext': secret_access_key_ciphertext,
        'SessionToken': resp['Credentials']['SessionToken']
    }
