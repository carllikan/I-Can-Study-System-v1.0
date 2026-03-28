######## Variables that need to be set from Bitbucket repository variables
variable "region"         { type = string }
# variable "zone"           { type = string }
variable "project_id"     { type = string }
variable "project_number" { type = string }

variable "deploy_firestore" { 
    type = bool 
    default = false
}

###########################################################################
###################### Variables for Cloud Functions ######################

############ cloud function processing documents searching ############
variable "name_cf_ics_document_process" {
    type =string
    default = "ics-document-process"
}

variable "source_files_ics_document_process" {
    type = list(string)
    default = [
        "../function_source/ics_document_process/main.py",
        "../function_source/ics_document_process/requirements.txt",
        "../function_source/common_py_utils/gcp.py",
    ]
}

variable "ics_document_process_available_cpu" {
    type = string
    default = "0.583"
}

variable "ics_document_process_available_memory_mb"{
    type = string
    default = "1Gi"
}


############ cloud function transcription processing ############
variable "name_cf_ics_transcript_process" {
    type =string
    default = "ics-transcript-process"
}

variable "source_files_ics_transcript_process" {
    type = list(string)
    default = [
        "../function_source/ics_transcript_process/main.py",
        "../function_source/ics_transcript_process/knn_tags.py",
        "../function_source/ics_transcript_process/requirements.txt",
        "../function_source/common_py_utils/gcp.py",
    ]
}

variable "ics_transcript_process_available_cpu" {
    type = string
    default = "1"
}

variable "ics_transcript_process_available_memory_mb"{
    type = string
    default = "2Gi"
}
############ cloud function video processing ############ 
variable "name_cf_ics_video_process" {
    type =string
    default = "ics-video-process"
}

variable "source_files_ics_video_process" {
    type = list(string)
    default = [
        "../function_source/ics_video_process/main.py",
        "../function_source/ics_video_process/requirements.txt",
        "../function_source/common_py_utils/gcp.py",
    ]
}

variable "ics_video_process_available_cpu" {
    type = string
    default = "0.583"
}

variable "ics_video_process_available_memory_mb"{
    type = string
    default = "1Gi"
}

############ cloud function initial table creation ############ 
variable "name_initial_table_creation" {
    type = string
    default = "initial_table_creation"
}

variable "source_files_initial_table_creation" {
    type = list(string)
    default = [
        "../function_source/initial_table_creation/main.py",
        "../function_source/initial_table_creation/requirements.txt",
        "../function_source/common_py_utils/gcp.py",
        "../function_source/common_py_utils/sql_orm.py",
    ]
}

############ cloud function initial firestore config ############ 
variable "name_initial_firestore_config" {
    type = string
    default = "initial_firestore_config"
}

variable "source_files_initial_firestore_config" {
    type = list(string)
    default = [
        "../function_source/initial_firestore_config/main.py",
        "../function_source/initial_firestore_config/requirements.txt",
        "../function_source/common_py_utils/gcp.py",
    ]
}

###################### Variables for Cloud Task queues ######################
variable "cloud_tasks_queue_mindmap_name" {
    type    = string
    default = "MindMapProcess-Queue"
}
variable "cloud_tasks_queue_reflection_name" {
    type    = string
    default = "ReflectionProcess-Queue"
}

###################### Variables for Artifact Registry Repository ###########
variable "cloud_run_repo" {
    type    = string
    default = "cloud-run-artifacts"
}

###################### Variables for Cloud SQL ######################
variable "database_instance_name" {
    type = string
    default = "ics-test-mysql"
}

variable "database_name" {
    type = string
    default = "ics-ai-jobs"
}

###################### Variables for Secret Manager ######################

# This is the name of the variable in the secrets This must match the configuration
# So when you want the pinecone api key you lookup secret('pinecone_api_key_name')
variable "pinecone_api_key_name"   {
    type = string
    default = "pinecone_api_key_name"
}

# This is the name of the variable in the secrets This must match the configuration
# So when you want the openai api key you lookup secret('openai_api_key_name')
variable "openai_api_key_name"   {
    type = string
    default = "openai_api_key_name"
}

# This is the name of the variable in the secrets This must match the configuration
# So when you want the cloud sql key you lookup secret('cloud_sql_key_name')
variable "cloud_sql_key_name"   {
    type = string
    default = "cloud_sql_key_name"
}


# This is the name of the variable in the secrets This must match the configuration
# So when you want the cloud sql key you lookup secret('api_key_name')
variable "api_key_name"   {
    type = string
    default = "api_key_name"
}


# This is the name of the variable in the secrets This must match the configuration
# So when you want the hf_access_token you lookup secret('hf_access_token_name')
variable "hf_access_token_name"   {
    type = string
    default = "hf_access_token_name"
}

# This is the name of the variable in the secrets This must match the configuration
# So when you want aws_access_key_id you lookup secret('aws_access_key_name')
variable "aws_access_key_name"   {
    type = string
    default = "aws_access_key_name"
}

# This is the name of the variable in the secrets This must match the configuration
# So when you want the haws_secret_access_key you lookup secret('aws_secret_access_key_name')
variable "aws_secret_access_key_name"   {
    type = string
    default = "aws_secret_access_key_name"
}

# This is defined by the environment varible passed in from the pipeline variables
variable "pinecone_api_key"   {type = string}
variable "openai_api_key"   {type = string}
variable "cloud_sql_password" {type = string}
variable "api_key_password" {type = string}
variable "hf_access_token" {type= string}
variable "aws_access_key_id" {type= string}
variable "aws_secret_access_key" {type= string}