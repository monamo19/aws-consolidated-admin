import boto3
import copy
import cfnresponse

# Lambda custom resource for managing CloudTrail Event Selectors.
# Allows you to use CloudFormation to configure the type of management
# events logged to a trail (ReadOnly, WriteOnly, None, or All) in
# addition to S3 access logging to CloudTrail.
#
# This resource DOES NOT change the read/write selector for management
# events if ManagementEventReadWriteType is undefined. Additionally,
# it will not modify the selection settings for any S3 bucket not
# defined in the resource's properties.
#
# This resource DOES have a race condition; an unintended overwrite of
# the trail's event selector configuration can occur if it changes
# after the existing settings are fetched. For this reason, do not
# invoke this resource twice from the same template.
#
# Usage (in the Resources block of your template):
#
#   CloudTrailEventSelectors:
#     Type: Custom::CloudTrailEventSelector
#     Properties:
#       ServiceToken: !GetAtt CloudTrailEventSelectorResourceFn.Arn
#       TrailName: !Ref CloudTrail
#       ManagementEventReadWriteType: All
#       DataEventSelectors:
#         All:
#           'AWS::S3::Object':
#             - !Sub 'arn:aws:s3:::${CloudTrailBucket}/'
#             - !Sub 'arn:aws:s3:::${ConfigBucket}/'
#         WriteOnly:
#           'AWS::S3::Object':
#             - !Sub 'arn:aws:s3:::${OtherS3Bucket}/'

cloudtrail = boto3.client('cloudtrail')

# Convert the API's representation of event selectors into something
# more manageable by converting lists with unique keys into dicts
def parse_event_selectors(source_event_selectors):
    event_selectors = {}
    for selector in copy.deepcopy(source_event_selectors):
        event_selectors[selector.pop('ReadWriteType')] = selector
        for data_resource in selector.pop('DataResources'):
            type_ = data_resource['Type']
            values = data_resource['Values']
            selector.setdefault('DataResources', {})[type_] = set(values)

    return event_selectors

# Convert from our representation of event selectors back into the
# API's representation
def format_event_selectors(event_selectors):
    resp = []
    for rwtype, es in event_selectors.iteritems():
        es['ReadWriteType'] = rwtype
        es['DataResources'] = [
            { 'Type': k, 'Values': list(v) } for k, v in
            es.pop('DataResources', {}).iteritems()]

        if len(es['DataResources']) > 0 or es['IncludeManagementEvents']:
            resp.append(es)
    return resp

def mutate_selectors(existing_selectors, defined_selectors, delete=False):
    for rwtype, defined_selector in defined_selectors.iteritems():
        selector = existing_selectors.setdefault(
            rwtype, {'IncludeManagementEvents': False})

        for type_, values in defined_selector.iteritems():
            resource_values = (selector
                               .setdefault('DataResources', {})
                               .setdefault(type_, set()))

            if delete:
                resource_values.difference_update(set(values))
            else:
                resource_values.update(set(values))

def mutate_management_event_selector(existing_selectors, mgmt_rw_type):
    # Reset all IncludeManagementEvents flags
    for _, selector in existing_selectors.iteritems():
        selector['IncludeManagementEvents'] = False

    existing_selectors.setdefault(
        mgmt_rw_type, {})['IncludeManagementEvents'] = True

def modify_event_selectors(request_type, props, old_props=None):
    resp = cloudtrail.get_event_selectors(TrailName=props['TrailName'])
    selectors = parse_event_selectors(resp['EventSelectors'])

    if request_type == 'Delete':
        mutate_selectors(selectors, props['DataEventSelectors'], True)
    else:
        if request_type == 'Update':
            mutate_selectors(selectors, old_props['DataEventSelectors'], True)

        mutate_selectors(selectors, props['DataEventSelectors'])

    try:
        mutate_management_event_selector(
            selectors, props['ManagementEventReadWriteType'])
    except KeyError:
        pass

    new_selectors = format_event_selectors(selectors)
    print new_selectors

    cloudtrail.put_event_selectors(
        TrailName=props['TrailName'], EventSelectors=new_selectors)

def handler(event, context):
    print event

    try:
        modify_event_selectors(
            event['RequestType'],
            event['ResourceProperties'],
            event.get('OldResourceProperties'))
    except Exception as e:
        print e.message
        response_code = cfnresponse.FAILED
    else:
        response_code = cfnresponse.SUCCESS

    cfnresponse.send(event, context, response_code, {},
                     event['ResourceProperties']['TrailName'])
