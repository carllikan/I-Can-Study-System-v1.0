***Overveiw of Pipleines Deployment for ICS***

Basically, this repository is going to be used to automatically deploy all pipelines on GCP for ICS to different enviroments. The automatied deployment combines **Terraform** and **Bitbucket Pipeline**.
**Development branch**: fix/pipeline-standardisation

---

## Structure of Repo

This repository includes 9 main folders, named **api_gateway_source**,**cloudrun_source**,**function_source** and **6 terraform folders** respectively.

1. **api_gateway_source**: This folder contains necessary source files (i.e. openapi.yml) used to create an API Gateway. There would be three API gateways created, respectively for ics-mind-map-evaluation, ics-document-search-evaluation and reflection-evaluation.

2. **cloudrun_source**: This folder contains necessary source files (i.e.app scripts, Dockerfile) use to create a cloud run service. Totally, four cloud run services would be created, three for APIs (simple web applications), one for **ics-mind-map-evaluation-pipeline**.

3. **function_source**: This folder includes the sources files which is used to create cloud functions. There are totally 3 cloud functions deployed, respectively with **ics_document_process**, **ics_transcript_process**, and **ics_video_process**.

4. **terraform folders**: It contains all Terraform scirpts that the deployment needs.


---

## Statistics of Resources

For all resources need to be deployed for ICS.

1. 6 cloud storage buckets 
2. 7 cloud run services
3. 5 cloud functions
4. 1 API gateways (keep the older one for internal test)
5. 1 cloud sql
6. 7 cloud secrets
7. 2 cloud task queues
8. 1 load balancer
9. cloud armor policy

---

## Deployment Enviroment
1. dev
2. test
3. prepro
4. pro

---

## Enviromental Variables Description

**ENV**: project name, which has been specified in the **bitbucekt-pipelines.yml**

**PROJECT**: project id, which has been set up in the bitbucket repository enviromental variables.

**SERVICE_ACCOUNT_EMAIL**: google service account emails, the emails for each project enviroment would be set up in the repository variables.

**KEY_FILE**: encoded json string in Base64, which is specified as repository envirables for each project enviroments in a security mode.

**REGION**: the project region

**PINECONE_API_KEY** used for connect Pinecone vector store

**PINECONE_ENV** the Pinecone enviroment

**OPENAI_API_KEY** the OpenAI API key to use OpenAI service

**CLOUD_SQL_PASSWORD** used to connect Cloud SQL *

**HF_ACCESS_TOKEN** used to access model checkpoints saved in Hugging Face repository

**API_KEY** used to authenticate the evaluation api

**AWS_ACCESS_KEY_ID** key id to access AWS

**AWS_SECRET_ACCESS_KEY** secret key to access AWS

**CALLBACK_URL** redirect URL for the environment

****

*Note*:

1. Any new enviromental variables should be added under the setting **Repository settings** scroll down to **Repository variables**.

2. Currently cloud sql used MySQL as database.

3. All sensitive keys like PINECONE_API_KEY, CLOUD_SQL_PASSWORD have managed by secrete manager.

---

## Specific Steps of Deployment


## Step 1:
Setup environmental Variables for ICS Deployment

 

## Step 2:
Delopy Some Necessary Resources

#### 1st Run Terraform
1. Build cloud storage buckets, cloud functions, secrets in the secret manager, cloud task queues, and the cloud SQL database instance. 
2. Run the initial firestore config and table creation functions to configure the two databases.

 

## Step 3:
Deploy global search and final feedback cloud run services

#### 2nd Run Terraform
1. Build and push images for the global search api cloud run service and final feedback cloud run service.
2. Deploy global search api cloud run service (needs to connect cloud SQL).
3. Deploy final feedback cloud run service（needs to connect cloud SQL).

 

## Step 4:
Deploy reflection evaluation pipeline cloud run

#### 3rd Run Terraform
1. Build and push images for the reflection evaluation pipeline cloud run service.
2. Depoy reflection evaluation pipeline（needs to connect cloud sql and use URL from final feedback cr)



## Step 5:
Deploy mind map evaluation pipeline cloud run

#### 4th Run Terraform
1. Build and push images for the mind map evaluation pipeline cloud run service.
2. Build and push docker for mind map evaluation pipeline（needs to connect cloud sql), deploy a cloud run service for it.

 

## Step 6:
Deploy the remaining cloud run resources (reflection/mindmap evaluation api and evaluation api cloud run services)

#### 5th Run Terraform
1. Build and push images for the three cloud run services
2. Deploy mind map evaluation api cloud run (using url from mind map evaluation pipeline); 
3. Deploy reflection evaluation api cloud run (using url from reflection evaluation pipeline); 
4. and Deploy evaluation api cloud run (needs to connect cloud sql and use both urls from mind map evaluation pipeline and reflection evaluation pipeline)

 

## Step 7:
Deploy evaluation api gateway, HTTP load balancer and the cloud armor policy

#### 6th Run Terraform
1. Deploy evaluation api gateway (using URLs from global search, mind map evaluation pipeline, reflection evaluation pipeline, and evaluation API cloud run services)
2. Deploy HTTP load balancer (the evaluation api gateway is used in the load balancer backend service)
3. Deploy the cloud armor policy (the HTTP load balancer is used as the target)

*Note*:

The deployment of all cloud run services has to follow corresponding order.

---
