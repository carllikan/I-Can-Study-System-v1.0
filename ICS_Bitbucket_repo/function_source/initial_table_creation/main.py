from sql_orm import *
def main(request):
    """This cloud function will automatically create all the cloud SQL tables
    Tables are listed in the sql_rom function
    """
    engine = initial_engine()
    create_all_tables(engine)
    return "cloud sql table created.", 200