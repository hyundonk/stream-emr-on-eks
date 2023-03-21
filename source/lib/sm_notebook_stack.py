# // Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# // SPDX-License-Identifier: License :: OSI Approved :: MIT No Attribution License (MIT-0)
#
from constructs import Construct
from aws_cdk import (Fn,Aws,NestedStack,RemovalPolicy,aws_sagemaker as sm)
from aws_cdk.aws_iam import IRole 
from aws_cdk.aws_ec2 import (IVpc,SecurityGroup,Port,Peer)

class NotebookStack(NestedStack):

    def __init__(self, scope: Construct, id: str, livy_sg:str, eksvpc: IVpc, sagemaker_role:IRole, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        # setup env variables
        my_on_create_script = """
        #!/bin/bash
        set -ex

        export clusterid=$(aws emr list-clusters --active  --query 'Clusters[?Name==`emr-roadshow`].Id' --output text)
        export engineer_role_arn=$(aws iam list-roles --query 'Roles[?contains(RoleName,`engineer`)].Arn' --output text)
        export analyst_role_arn=$(aws iam list-roles --query 'Roles[?contains(RoleName,`analyst`)].Arn' --output text)

        echo "export CLUSTERID=${clusterid}" | tee -a ~/.bashrc
        echo "export ENGINEER_ROLE=${engineer_role_arn}" | tee -a ~/.bashrc
        echo "export ANALYST_ROLE=${analyst_role_arn}" | tee -a ~/.bashrc
        source ~/.bashrc
        """

        sparkmagic_conf=sm.CfnNotebookInstanceLifecycleConfig(self, "oncreate_conf",
            notebook_instance_lifecycle_config_name="sparkmagic-config",
            on_create=[sm.CfnNotebookInstanceLifecycleConfig.NotebookInstanceLifecycleHookProperty(
                content=Fn.base64(my_on_create_script)
            )])
        sm_sg=SecurityGroup.from_security_group_id(self, "notebook_sg", eksvpc.vpc_default_security_group,mutable=False)
        sm_notebook=sm.CfnNotebookInstance(self, "notebook", 
            notebook_instance_name="emr-runtime-lf-notebook",
            instance_type="ml.t3.medium",
            role_arn=sagemaker_role.role_arn,
            subnet_id=eksvpc.private_subnets[0].subnet_id,
            direct_internet_access="Disabled",
            security_group_ids=[sm_sg.security_group_id],
            volume_size_in_gb = 10,
            lifecycle_config_name="sparkmagic-config"
        )
        # Allow Sagemaker notebook access Livy in EMR  
        self.emr_master_sg=SecurityGroup.from_security_group_id(self,"AdditionalSG",livy_sg)
        self.emr_master_sg.connections.allow_from(sm_sg, Port.tcp(8998), "open Livy port to SM")