import gui
from sqlalchemy import inspect, MetaData, text
from sqlalchemy.schema import Column


def generate_column_definition(column, engine):
    column_name = column.name
    column_type = column.type.compile(engine.dialect)
    column_attributes = [str(attr) for attr in column.constraints]
    column_definition = f"{column_name} {column_type}"
    if column_attributes:
        column_definition += " " + " ".join(column_attributes)
    return column_definition


def merge_metadata(*original_metadata) -> MetaData:
    merged = MetaData()
    for original_metadatum in original_metadata:
        for table in original_metadatum.tables.values():
            table.to_metadata(merged)
    return merged


def get_columns(insp, table_name, schema):
    return insp.get_columns(table_name, schema=schema)


def _handle_missing_columns(
    table_name, missing_columns_table1, missing_columns_table2, session, table2, engine
):
    result = ""
    if missing_columns_table2:
        result += f"Missing columns in local '{table_name}': {', '.join(missing_columns_table2)}\n"
    if missing_columns_table1:
        result += f"Missing columns in remote '{table_name}': {', '.join(missing_columns_table1)}\n"
        for miss in missing_columns_table1:
            # Add missing columns to remote.
            # This is primarily intended for SQLite3.
            col: Column = table2.columns[miss]
            alter_table_stmt = text(
                f"ALTER TABLE {table_name} ADD COLUMN {generate_column_definition(col, engine)};"
            )
            session.execute(alter_table_stmt)
            session.commit()
    return result


def _get_tables_meta(db_meta: MetaData, merged: MetaData):
    return db_meta.tables, merged.tables


async def _async_handle_missing_columns(
    table_name, missing_columns_table1, missing_columns_table2, session, table2, engine
):
    result = ""
    if missing_columns_table2:
        result += f"Missing columns in local '{table_name}': {', '.join(missing_columns_table2)}\n"
    if missing_columns_table1:
        result += f"Missing columns in remote '{table_name}': {', '.join(missing_columns_table1)}\n"
        for miss in missing_columns_table1:
            # Add missing columns to remote.
            # This is primarily intended for SQLite3.
            col: Column = table2.columns[miss]
            alter_table_stmt = text(
                f"ALTER TABLE {table_name} ADD COLUMN {generate_column_definition(col, engine)};"
            )
            await session.execute(alter_table_stmt)
            await session.commit()
    return result


def _compare_tables(table_name, tables1, tables2, insp, session, engine):
    result = ""
    table1 = tables1.get(table_name)
    table2 = tables2.get(table_name)
    if table1 is None:
        result += f"Table '{table_name}' is missing from remote.\n"
    elif table2 is None:
        result += f"Table '{table_name}' is missing from local.\n"
    else:
        columns1 = get_columns(insp, table_name, schema=table1.schema)
        columns2 = [
            {
                "name": column.name,
                "type": column.type,
                "nullable": column.nullable,
                "origcol": column,
            }
            for column in table2.columns
        ]

        column_names1 = set(column["name"] for column in columns1)
        column_names2 = set(column["name"] for column in columns2)

        missing_columns_table2 = column_names1 - column_names2
        missing_columns_table1 = column_names2 - column_names1

        if missing_columns_table2 or missing_columns_table1:
            out = _handle_missing_columns(
                table_name,
                missing_columns_table1,
                missing_columns_table2,
                session,
                table2,
                engine,
            )
            gui.gprint("THO", out)
            result += out
    return result


async def _async_compare_tables(table_name, tables1, tables2, session, engine):
    result = ""
    table1 = tables1.get(table_name)
    table2 = tables2.get(table_name)
    if table1 is None:
        result += f"Table '{table_name}' is missing from remote.\n"
    elif table2 is None:
        result += f"Table '{table_name}' is missing from local.\n"
    else:
        async with engine.begin() as async_conn:

            def get_columns(conn, table_name, schema):
                insp = inspect(conn)
                gui.gprint(table_name, schema, insp)
                return insp.get_columns(table_name, schema=schema)

            columns1 = await async_conn.run_sync(
                get_columns, table_name, schema=table1.schema
            )

        columns2 = [
            {
                "name": column.name,
                "type": column.type,
                "nullable": column.nullable,
                "origcol": column,
            }
            for column in table2.columns
        ]

        column_names1 = set(column["name"] for column in columns1)
        column_names2 = set(column["name"] for column in columns2)

        missing_columns_table2 = column_names1 - column_names2
        missing_columns_table1 = column_names2 - column_names1

        if missing_columns_table2 or missing_columns_table1:
            result += await _async_handle_missing_columns(
                table_name,
                missing_columns_table1,
                missing_columns_table2,
                session,
                table2,
                engine,
            )
    return result


def compare_db(self):
    """compare current metadata with sqlalchemy metadata"""
    insp = inspect(self.engine)
    db_meta = MetaData()
    db_meta.reflect(bind=self.engine)
    mt = [base.metadata for base in self.bases]
    merged = merge_metadata(*mt)

    tables1, tables2 = _get_tables_meta(db_meta, merged)

    result = ""
    session = self.get_session()

    for table_name in set(tables1) | set(tables2):
        result += _compare_tables(
            table_name, tables1, tables2, insp, session, self.engine
        )

    return result


async def async_compare_db(self):
    """compare current metadata with sqlalchemy metadata"""

    db_meta = MetaData()
    async with self.aengine.begin() as conn:
        await conn.run_sync(db_meta.reflect)
    mt = [base.metadata for base in self.bases]
    merged = merge_metadata(*mt)

    tables1, tables2 = _get_tables_meta(db_meta, merged)

    result = ""
    async with self.get_async_session() as session:
        for table_name in set(tables1) | set(tables2):
            result += await _async_compare_tables(
                table_name, tables1, tables2, session, self.aengine
            )

    return result
