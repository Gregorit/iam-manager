#!/bin/env python3
import boto3
import pandas
import time 
import csv
import athena_from_s3
import json
from collections import defaultdict
from pprint import pprint as pp
from botocore.exceptions import ClientError


# role_user_group_arn = "arn:aws:iam::789552300344:user/akurow"
role_user_group_arn = event['queryStringParameters']['arn']


def handler(event, context):  
    params = {
        'region' : 'eu-west-1',
        'database' : 'cloudtrail',
        'bucket' : 'iam-manager-cloudtrails310cd22f2-faslq2t36wt4',
        'path'  : 'athena_out',
        'query': f'SELECT * FROM "cloudtrail"."trail_logs" WHERE "useridentity"."arn"  = \'{role_user_group_arn}\''
        }
    session = boto3.session.Session()
    location, data= athena_from_s3.query_results(session, params)
    print("Locations", location)
    print("Result Data: ")
    pp(data['Rows'][1]['Data'])


    rights = defaultdict(int)

    ignore_list = ["signin", "tagging", "monitoring"]
    iterate = len(data['Rows'])
    for i in range(1,iterate):
        row = data['Rows'][i]
        if row['Data'][3]['VarCharValue'].split('.')[0] in ignore_list:
            continue

        e1 = row['Data'][3]['VarCharValue'].split('.')[0]
        e2 = row['Data'][4]['VarCharValue']
        reg = row['Data'][5]['VarCharValue']
        # param = row['Data'][10]['VarCharValue']
        acc_id = row['Data'][19]['VarCharValue']
        right =  f'arn:aws:{e1}:{reg}:{acc_id}:{e2}:*'
        rights[right] += 1


    print(f"Single: {rights[1]}\n\n")
    rights_list = [key for key, value in rights.items() if value > 0]
    pp(rights_list)


    generated_policy = {
        "Version": "2012-10-17",
        "Statement": []
        }

    services_list = []
    for right in rights_list:
        right = right.split(':')

        if right[2] not in services_list:
            services_list.append(right[2])
            generated_policy['Statement'].append({
                "Effect": "Allow",
                "Action": [],
                "Resource": []
                })


        action = f"{right[2]}:{right[5]}"
        dest = generated_policy['Statement'][services_list.index(right[2])]['Action']
        if action not in dest:
            dest.append(action)
        
        resource = f"{right[0]}:{right[1]}:{right[2]}:::*"
        dest = generated_policy['Statement'][services_list.index(right[2])]['Resource']
        if resource not in dest:
            dest.append(resource)


    # Check if policy exists, remove it if yes
    try:
        iam = session.client('iam')
        iam.create_policy(
            PolicyName = "generated-policy",
            PolicyDocument = json.dumps(generated_policy)
        )
    except ClientError:
        # Detach policy
        iam = boto3.resource('iam')
        group = iam.Group('tester')
        group.detach_policy(
            PolicyArn=f'{right[0]}:{right[1]}:iam::{right[4]}:policy/generated-policy'
        )

        # Remove old policy and add new one
        iam = session.client('iam')
        iam.delete_policy(
            PolicyArn=f"{right[0]}:{right[1]}:iam::{right[4]}:policy/generated-policy"
        )
        iam.create_policy(
            PolicyName = "generated-policy",
            PolicyDocument = json.dumps(generated_policy)
        )

    # Attach policy to role
    iam = boto3.resource('iam')
    group = iam.Group('tester')
    group.attach_policy(
        PolicyArn=f'{right[0]}:{right[1]}:iam::{right[4]}:policy/generated-policy'
    )

    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'text/plain'
        },
        'body': 'Learner finished with code 0.'
    }