from sqlalchemy import MetaData, select
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from sqlalchemy import select, delete, func
from sqlalchemy.dialects.sqlite import insert
from typing import List, Type, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.expression import Insert


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


async def add_or_update_all_a(session: AsyncSession, model_class, data_list):
    insert_data = []
    for data in data_list:
        primary_key_name, primary_key_value = get_primary_key(data)
        filter_kwargs = {primary_key_name: primary_key_value}

        db_stm = await session.execute(select(model_class).filter_by(**filter_kwargs))
        db_obj = db_stm.scalar_one_or_none()
        if db_obj is None:
            insert_data.append(data)
        else:
            pass
    if insert_data:
        session.add_all(insert_data)


async def upsert_a(
    session: AsyncSession,
    model: Any,
    index_elements: List[str],
    values_list: List[Dict[str, Any]],
    do_commit: bool = True,
) -> None:
    stmt: Insert = insert(model)
    do_update_stmt = stmt.on_conflict_do_update(
        index_elements=index_elements,
        set_={
            key: getattr(stmt.excluded, key)
            for key in values_list[0].keys()
            if key not in index_elements
        },
    )
    await session.execute(do_update_stmt, values_list)
    if do_commit:
        await session.commit()


def merge_metadata(*original_metadata) -> MetaData:
    merged = MetaData()

    for original_metadatum in original_metadata:
        for table in original_metadatum.tables.values():
            table.to_metadata(merged)

    return merged


async def get_entries_in_batches(session, model_class, filter_condition, batch_size):
    query = session.query(model_class).filter(filter_condition)
    offset = 0
    entries_batch = query.offset(offset).limit(batch_size).all()
    while entries_batch:
        yield entries_batch
        offset += batch_size
        entries_batch = query.offset(offset).limit(batch_size).all()
