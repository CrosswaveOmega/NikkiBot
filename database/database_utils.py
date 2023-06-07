from sqlalchemy import MetaData
from sqlalchemy.orm import Session

def get_primary_key(instance):
    primary_key_cols = instance.__mapper__.primary_key
    primary_key_name = primary_key_cols[0].name
    primary_key_value = getattr(instance, primary_key_name)
    return (primary_key_name, primary_key_value)
def add_or_update_all(session: Session, model_class, data_list):
    insert_data = []
    for data in data_list:
        primary_key_name, primary_key_value = get_primary_key(data)
        filter_kwargs = {primary_key_name: primary_key_value}
        db_obj = session.query(model_class).filter_by(**filter_kwargs).first()
        if db_obj is None:
            insert_data.append(data)
        else:
            pass
    if insert_data:
        session.add_all(insert_data)

def merge_metadata(*original_metadata) -> MetaData:
    merged = MetaData()

    for original_metadatum in original_metadata:
        for table in original_metadatum.tables.values():
            table.to_metadata(merged)
    
    return merged