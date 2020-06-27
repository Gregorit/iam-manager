from aws_cdk import (
    core,
    aws_apigateway as agw,
    aws_lambda as lambda_,
    aws_cloudtrail as cloudtrail,
    aws_glue as glue,
    aws_athena as athena,
    aws_s3 as s3,
    aws_iam as iam,
    aws_route53 as route53,
    aws_certificatemanager as certmanager,
    aws_cloudfront  as cloudfront,
    aws_codepipeline as codepipeline,
    aws_codebuild as codebuild,
    aws_codepipeline_actions as pipeline_actions
)
# from static_website import StaticWebsite


class IamManagerStack(core.Stack):

    def __init__(self, scope: core.Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        # Lambdas and Api GW
        api = agw.RestApi(self, "learner-api",
            rest_api_name="Learner Service",
            description="System to learn roles")    
        
        
        switcher = lambda_.Function(self,"Switcher",
            runtime = lambda_.Runtime.PYTHON_3_8,
            code =  lambda_.Code.from_asset("lambdas/switcher"),
            handler = "main.handler",
        )

        frontend = lambda_.Function(self,"Frontend",
            runtime = lambda_.Runtime.PYTHON_3_8,
            code =  lambda_.Code.from_asset("lambdas/frontend"),
            handler = "main.handler",
 
        )
        learner = lambda_.Function(self,"Learner",
            runtime = lambda_.Runtime.PYTHON_3_8,
            code =  lambda_.Code.from_asset("lambdas/learner"),
            handler = "main.handler",
        )


        get_switcher_integration = agw.LambdaIntegration(switcher,
                request_templates={"application/json": '{ "statusCode": "200" }'})

        get_frontend_integration = agw.LambdaIntegration(frontend,
                request_templates={"application/json": '{ "statusCode": "200" }'})
        
        get_learner_integration = agw.LambdaIntegration(learner,
                request_templates={"application/json": '{ "statusCode": "200" }'})

        api.root.add_method("GET", get_frontend_integration) 
        
        switch = api.root.add_resource('switch')
        switch.add_method("GET",get_switcher_integration)

        learn = api.root.add_resource('learn')
        learn.add_method("GET",get_learner_integration)

        # CloudTrail 
        bucket = s3.Bucket(self,'TrailBucket',
            versioned = True
        )
        tail = cloudtrail.Trail(self,'CloudTrail',bucket=bucket)

        db_name = 'cloudtrail'
        db = glue.Database(self,'cloudtrail',database_name=db_name)

        awg = core.CfnResource(self,'AthenaWorkGroup',
            type = "AWS::Athena::WorkGroup",
            properties={
                "Name" : "IAMManagerWorkgroup",
                "State":"ENABLED",
                "WorkGroupConfiguration":{
                    "ResultConfiguration":{
                        "OutputLocation":f"s3://{bucket.bucket_name}/athena_output/"
                    }
                }

            }
            )

        # Static Website
        domain_name = "grzes.darevee.pl"
        zone = route53.PublicHostedZone(self,'GrzesDomain',
            zone_name = domain_name
        )

        # Content bucket
        site_bucket = s3.Bucket(self, "SiteBucket",
                                    website_index_document="index.html",
                                    website_error_document="404.html",
                                    public_read_access=True,
                                    removal_policy=core.RemovalPolicy.DESTROY)
        cert = certmanager.DnsValidatedCertificate(self, "PublicBucketCert", domain_name=domain_name, hosted_zone=zone)
        

        # Pipeline for Working on Data
        project = codebuild.PipelineProject(self,'main_pipeline_project',
            build_spec = codebuild.BuildSpec.from_source_filename('buildspec.yml')
        )
        project.role.add_managed_policy(iam.ManagedPolicy.from_aws_managed_policy_name("AdministratorAccess"))

        source_output = codepipeline.Artifact()

        source_action = pipeline_actions.S3SourceAction(
            action_name = 'S3Source',
            bucket = bucket,
            bucket_key = 'pipeline/learner.zip',
            output = source_output
        )

        build_action = pipeline_actions.CodeBuildAction(
            action_name = 'CodeBuild',project = project,input = source_output,

        )
        codepipeline.Pipeline(self,'main_pipeline',
            stages = [
                {'stageName':  'Source','actions': [source_action]  },
                {'stageName': 'Build','actions': [build_action]}
            ]
        )

        # Outputs
        core.CfnOutput(self,'BucketName',value=bucket.bucket_name)








    
        



