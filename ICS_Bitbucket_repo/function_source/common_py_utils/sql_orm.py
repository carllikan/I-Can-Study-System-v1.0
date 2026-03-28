from sqlalchemy import create_engine, Column, String, DateTime, Text, ForeignKey
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
from gcp import *

logger = gcp_logger()
run_conf = gcp_get_config()
project_id = gcp_project_id()
Base = declarative_base()

class EvalApiJobs(Base):
    __tablename__ = 'eval_api_jobs'
    job_id = Column(String(255), primary_key=True)
    start_timestamp = Column(DateTime)
    request = Column(Text)
    end_timestamp = Column(DateTime)

class JobsForSubmission(Base):
    __tablename__ = 'jobs_for_submission'
    job_id = Column(String(255), primary_key=True)
    learner_id = Column(String(255))

class EvalApiComponentJobs(Base):
    __tablename__ = 'eval_api_component_jobs'
    job_id = Column(String(255))
    sub_component_type = Column(String(255))
    sub_component_job_id = Column(String(255), primary_key=True)

class MindmapJobs(Base):
    __tablename__ = 'mindmap_jobs'
    mindmap_job_id = Column(String(255), primary_key=True)
    eval_job_id = Column(String(255))
    start_timestamp = Column(DateTime)
    request = Column(Text)
    end_timestamp = Column(DateTime)

class ReflectionJobs(Base):
    __tablename__ = 'reflection_jobs'
    reflection_job_id = Column(String(255), primary_key=True)
    eval_job_id = Column(String(255))
    start_timestamp = Column(DateTime)
    request = Column(Text)
    end_timestamp = Column(DateTime)

class TextJobs(Base):
    __tablename__ = 'text_jobs'
    text_job_id = Column(String(255), primary_key=True)
    eval_job_id = Column(String(255))
    start_timestamp = Column(DateTime)
    request = Column(Text)
    end_timestamp = Column(DateTime)

class GlobalSearchQueries(Base):
    __tablename__ = 'global_search_queries'
    query_id = Column(String(255), primary_key=True)
    user_id = Column(String(255))
    query_timestamp = Column(DateTime)
    query_content = Column(Text)
    query_type = Column(Text)

class GlobalSearchResponses(Base):
    __tablename__ = 'global_search_responses'
    response_id = Column(String(255), primary_key=True)
    query_id = Column(String(255))
    response_timestamp = Column(DateTime)
    response_content = Column(Text)
    
def initial_engine():
    # Define the database connection parameters
    project_number = gcp_project_number(project_id)
    db_user = run_conf.get( 'sqldb_user', 'root' )
    db_pass = gcp_get_secret(project_number,run_conf.get( 'sqldb_password', 'cloud_sql_key_name' ))
    db_name = run_conf.get( 'sqldb_database', 'ics-ai-jobs' )
    project = project_id
    region = run_conf.get( 'region', 'us-west2' )
    instance_name = run_conf.get( 'sqldb_instance', 'ics-test-mysql' )
    db_instance = f"{project}:{region}:{instance_name}"

    # Construct the connection URL
    db_url = f"mysql+pymysql://{db_user}:{db_pass}@/{db_name}?unix_socket=/cloudsql/{db_instance}"
    logger.debug(f"database_connection_url: {db_url}")
    # Create the SQLAlchemy engine
    engine = create_engine(db_url)

    return engine

def create_all_tables(engine):
    # Create the tables
    Base.metadata.create_all(engine)
    logger.debug(f"tables are created.")

def evalApiComponentJobs_insert(engine, query):
    # Create a session to interact with the database
    Session = sessionmaker(bind=engine)
    session = Session()

    # Extract values from query json
    main_job_id = query.get("job_id", "")
    sub_component_type = query.get("sub_component_type","")
    sub_component_job_id = query.get("sub_component_job_id", "")

    # Check if a record with the same sub_component_job_id already exists
    existing_job = session.query(EvalApiComponentJobs).filter_by(sub_component_job_id=sub_component_job_id).first()

    if existing_job:
        # Update existing record
        logger.debug(f"sub_component_job_id: {existing_job.sub_component_job_id} already exists")
    else:
        # Insert a new record
        new_job = EvalApiComponentJobs(job_id=main_job_id, sub_component_type=sub_component_type, sub_component_job_id=sub_component_job_id)
        session.add(new_job)
        session.commit()
    # Example: Query records from EvalApiJobs
    jobs = session.query(EvalApiComponentJobs).all()
    for job in jobs:
        logger.debug(f"Job ID: {job.job_id}, Sub Component Type: {job.sub_component_type}")

    # Remeber to close the session when done
    session.close()

def mindmapJobs_insert(engine, query):
    # Create a session to interact with the database
    Session = sessionmaker(bind=engine)
    session = Session()

    # Extract values from query json
    key_id = query.get("mindmap_job_id", "")
    eval_job_id = query.get("eval_job_id", "")
    start_timestamp = query.get("start_timestamp", datetime.now())
    request = query.get("request", "No request")
    end_timestamp = query.get("end_timestamp", start_timestamp)

    # Example: Insert a record into EvalApiJobs
    existing_job = session.query(MindmapJobs).filter_by(mindmap_job_id=key_id).first()

    if existing_job:
        # Update existing record
        logger.debug(f"mindmap_job_id: {existing_job.mindmap_job_id} already exists")
    else:
        # Insert a new record
        new_job = MindmapJobs(mindmap_job_id=key_id,eval_job_id=eval_job_id, start_timestamp=start_timestamp, request=request, end_timestamp=end_timestamp)
        session.add(new_job)
        session.commit()

    # Example: Query records from EvalApiJobs
    jobs = session.query(MindmapJobs).all()
    for job in jobs:
        logger.debug(f"Mind Map Job ID: {job.mindmap_job_id}, Start Timestamp: {job.start_timestamp}")

    # Remeber to close the session when done
    session.close()
    logger.debug("rows added.")

def reflectionJobs_insert(engine, query):
    # Create a session to interact with the database
    Session = sessionmaker(bind=engine)
    session = Session()

    # Extract values from query json
    key_id = query.get("reflection_job_id", "")
    eval_job_id = query.get("eval_job_id", "")
    start_timestamp = query.get("start_timestamp", datetime.now())
    request = query.get("request", "No request")
    end_timestamp = query.get("end_timestamp", start_timestamp)


    existing_job = session.query(ReflectionJobs).filter_by(reflection_job_id=key_id).first()

    if existing_job:
        # Update existing record
        logger.debug(f"reflection_job_id: {existing_job.reflection_job_id} already exists")
    else:
        # Insert a new record
        new_job = ReflectionJobs(
            reflection_job_id=key_id,
            eval_job_id=eval_job_id,
            start_timestamp=start_timestamp,
            request=request,
            end_timestamp=end_timestamp,
        )
        session.add(new_job)
        session.commit()

    # Example: Query records from EvalApiJobs
    jobs = session.query(ReflectionJobs).all()
    for job in jobs:
        logger.debug(f"Reflection Job ID: {job.reflection_job_id}, Start Timestamp: {job.start_timestamp}")

    # Remember to close the session when done
    session.close()
    logger.debug("Rows added to ReflectionJobs.")


def evalApiJobs_insert(engine, query):
    # Create a session to interact with the database
    Session = sessionmaker(bind=engine)
    session = Session()

    # Extract values from query json
    key_id = query.get("job_id", "")
    start_timestamp = query.get("start_timestamp", datetime.now())
    request = query.get("request", "No request")
    end_timestamp = query.get("end_timestamp", start_timestamp)

    # Example: Insert a record into EvalApiJobs


    existing_job = session.query(EvalApiJobs).filter_by(job_id=key_id).first()

    if existing_job:
        # Update existing record
        logger.debug(f"job_id: {existing_job.job_id} already exists")
    else:
        # Insert a new record
        new_job = EvalApiJobs(job_id=key_id, start_timestamp=start_timestamp, request=request, end_timestamp=end_timestamp)
        session.add(new_job)
        session.commit()


    # Example: Query records from EvalApiJobs
    jobs = session.query(EvalApiJobs).all()
    for job in jobs:
        logger.debug(f"Job ID: {job.job_id}, Start Timestamp: {job.start_timestamp}")

    # Remeber to close the session when done
    session.close()
    logger.debug("rows added.")


def evalApiJobs_query(engine, query):
    # Create a session to interact with the database
    Session = sessionmaker(bind=engine)
    session = Session()

    # Extract values from query json
    key_id = query.get("job_id", "")

    # Example: Insert a record into EvalApiJobs
    existing_job = session.query(EvalApiJobs).filter_by(job_id=key_id).first()

    return existing_job

def submissionJobs_insert(engine, query):
    # Create a session to interact with the database
    Session = sessionmaker(bind=engine)
    session = Session()

    # Extract values from query json
    key_id = query.get("job_id", "")
    learner_id = query.get("learner", "")

    # Insert a record into JobsForSubmission

    existing_job = session.query(JobsForSubmission).filter_by(job_id=key_id).first()

    if existing_job:
        # Update existing record
        logger.debug(f"job_id: {existing_job.job_id} already exists")
    else:
        # Insert a new record
        new_job = JobsForSubmission(job_id=key_id, learner_id=learner_id)
        session.add(new_job)
        session.commit()

    # Example: Query records from JobsForSubmission
    jobs = session.query(JobsForSubmission).all()
    for job in jobs:
        logger.debug(f"Job ID: {job.job_id}, Learner Id: {job.learner_id}")

    # Remeber to close the session when done
    session.close()
    logger.debug("rows added.")

def globalSearchQueries_insert(engine, query):

    Session = sessionmaker(bind=engine)
    session = Session()
    query_id = query.get("query_id", "")
    user_id = query.get("user_id", "")
    query_timestamp = query.get("query_timestamp", "")
    query_type = query.get("query_type", "")
    query_content = query.get("query_content", "")
    existing_job = session.query(GlobalSearchQueries).filter_by(query_id=query_id).first()

    if existing_job:
        # Update existing record
        logger.debug(f"job_id: {existing_job.query_id} already exists")
    else:
        # Insert a new record
        new_job = GlobalSearchQueries(query_id=query_id, user_id=user_id, query_timestamp=query_timestamp, query_type=query_type, query_content=query_content)
        session.add(new_job)
        session.commit()
    session.close()
    logger.debug("Global Search Queries rows added.")


def globalSearchResponses_insert(engine, query):

    Session = sessionmaker(bind=engine)
    session = Session()

    response_id = query.get("response_id", "")
    query_id = query.get("query_id", "")
    response_timestamp = query.get("response_timestamp", "")
    response_content = query.get("response_content", "")
    existing_job = session.query(GlobalSearchResponses).filter_by(response_id=response_id).first()

    if existing_job:
        # Update existing record
        logger.debug(f"job_id: {existing_job.response_id} already exists")
    else:
        # Insert a new record
        new_job = GlobalSearchResponses(response_id=response_id, query_id=query_id, response_timestamp=response_timestamp, response_content=response_content)
        session.add(new_job)
        session.commit()
    session.close()
    logger.debug("Global Search Responses rows added.")


def evalApiJobs_update(engine, query):
    # Create a session
    Session = sessionmaker(bind=engine)
    session = Session()

    # Extract values from query json
    job_id_to_update = query.get("job_id", "")
    end_timestamp = query.get("end_timestamp", datetime.now())

    # Query the database to retrieve the record to update
    job_to_update = session.query(EvalApiJobs).filter_by(job_id=job_id_to_update).first()

    # Check if the job exists
    if job_to_update:
        # Update the attributes of the job
        job_to_update.end_timestamp = end_timestamp

        # Commit the changes to the database
        session.commit()
        logger.debug(f"Job with ID '{job_id_to_update}' is updated.")
    else:
        logger.warn(f"Job with ID '{job_id_to_update}' not found.")

    # Close the session
    session.close()

def mindmapJobs_update(engine, query):
    # Create a session
    Session = sessionmaker(bind=engine)
    session = Session()

    # Extract values from query json
    mindmap_job_id_to_update = query.get("mindmap_job_id", "")
    # start_timestamp = query.get("start_timestamp", datetime.now())
    # request = query.get("request", "No request")
    end_timestamp = query.get("end_timestamp", datetime.now())

    # Query the database to retrieve the record to update
    job_to_update = session.query(MindmapJobs).filter_by(mindmap_job_id=mindmap_job_id_to_update).first()

    # Check if the job exists
    if job_to_update:
        # Update the attributes of the job
        # job_to_update.start_timestamp = start_timestamp
        # job_to_update.request = request
        job_to_update.end_timestamp = end_timestamp

        # Commit the changes to the database
        session.commit()
        logger.debug(f"Job with ID '{mindmap_job_id_to_update}' is updated.")
    else:
        logger.warn(f"Job with ID '{mindmap_job_id_to_update}' not found.")

    # Close the session
    session.close()

def reflectionJobs_update(engine, query):
    # Create a session
    Session = sessionmaker(bind=engine)
    session = Session()

    # Extract values from the query JSON
    reflection_job_id_to_update = query.get("reflection_job_id", "")
    end_timestamp = query.get("end_timestamp", datetime.now())

    # Query the database to retrieve the record to update
    job_to_update = session.query(ReflectionJobs).filter_by(reflection_job_id=reflection_job_id_to_update).first()

    # Check if the job exists
    if job_to_update:
        # Update the attributes of the job
        job_to_update.end_timestamp = end_timestamp

        # Commit the changes to the database
        session.commit()
        logger.debug(f"Reflection Job with ID '{reflection_job_id_to_update}' is updated.")
    else:
        logger.warning(f"Reflection Job with ID '{reflection_job_id_to_update}' not found.")

    # Close the session
    session.close()

def submissionJobs_update(engine, query):
    # Create a session
    Session = sessionmaker(bind=engine)
    session = Session()

    # Extract values from the query JSON
    submission_job_id_to_update = query.get("submission_job_id", "")
    learner_id = query.get("learner_id", "")

    # Query the database to retrieve the record to update
    job_to_update = session.query(JobsForSubmission).filter_by(job_id=submission_job_id_to_update).first()

    # Check if the job exists
    if job_to_update:
        # Update the attributes of the job
        job_to_update.learner_id = learner_id

        # Commit the changes to the database
        session.commit()
        logger.debug(f"Submission Job with ID '{submission_job_id_to_update}' is updated.")
    else:
        logger.warning(f"Reflection Job with ID '{submission_job_id_to_update}' not found.")

    # Close the session
    session.close()



