from __future__ import print_function
import pytest
import os
import glob
import functools
import psycopg2
from sqlpy import Queries, load_queries, SQLLoadException,\
    SQLParseException, SQLArgumentException, SQLpyException, parse_sql_entry, QueryType
import logging


@pytest.fixture()
def enable_logging():
    logging.basicConfig(level=logging.DEBUG,
                        format='%(asctime)s %(module)s %(levelname)s %(message)s')


@pytest.fixture
def queries_file():
    return os.path.join(os.getcwd(), 'test_queries.sql')


@pytest.fixture
def queries_file_arr():
    return [os.path.join(os.getcwd(), 'test_queries.sql')]


@pytest.fixture
def queries_file_glob():
    return glob.glob(os.path.join(os.getcwd(), '*.sql'))


@pytest.fixture
def invalid_file_path():
    return 'path_that_does_not_exist.sql'


@pytest.fixture
def invalid_sql_name_start():
    return """
-- nam: test_select
-- testing the sqlpi module pls work
SELECT * FROM testdb
""".strip('\n')


@pytest.fixture
def invalid_sql_name_spaces():
        return """
-- name: test select
-- testing the sqlpi module pls work
SELECT * FROM testdb
""".strip('\n')


@pytest.fixture
def invalid_sql_built():
        return """
-- name: test_built$
-- testing the sqlpi module pls work
SELECT * FROM testdb
WHERE 1=1
AND col_1 = %()s
""".strip('\n')


@pytest.fixture
def invalid_sql_built_args():
        return """
-- name: test_built$
-- testing the sqlpi module pls work
SELECT * FROM testdb
WHERE 1=1
AND col_1 = %(arg1)s
AND col_2 = %(arg1)
""".strip('\n')


@pytest.fixture
def sql_bang():
        return """
-- name: test_delete!
DELETE FROM testdb
""".strip('\n')


@pytest.fixture
def sql_bang_return():
        return """
-- name: test_return<!>
INSERT INTO test (col_1) VALUES ('A') RETURNING col_1
""".strip('\n')


@pytest.fixture
def sql_built():
        return """
-- name: test_built$
-- testing the sqlpi module pls work
SELECT * FROM testdb
WHERE 1=1
AND col_1 = %(val_1)s
""".strip('\n')


@pytest.fixture
def sql_proc():
        return """
-- name: test_proc_call@
example_fcn_name
""".strip('\n')


@pytest.fixture
def sql_select_1():
    return """
-- name: select_1
SELECT 1;
""".strip('\n')


@pytest.fixture(scope="module")
def db_cur():
    db_host = 'localhost'
    db_port = 5432
    db_user = 'postgres'
    db_pass = ''
    db = psycopg2.connect(dbname='postgres',
                          user=db_user,
                          password=db_pass,
                          host=db_host,
                          port=db_port)
    yield db.cursor()
    db.close()


class TestLoad:
    def test_load(self, queries_file):
        parsed = load_queries(queries_file)
        assert isinstance(parsed, list)

    def test_load_arr(self, queries_file_arr):
        parsed = load_queries(queries_file_arr)
        assert isinstance(parsed, list)

    def test_load_name(self, queries_file):
        parsed = load_queries(queries_file)
        assert parsed[0][0] == 'TEST_SELECT'

    def test_load_fcn(self, queries_file):
        parsed = load_queries(queries_file)
        assert isinstance(parsed[0][2], functools.partial)

    def test_load_fcn_name(self, queries_file):
        parsed = load_queries(queries_file)
        fcn = parsed[0][2]
        assert fcn.__name__ == 'TEST_SELECT'

    def test_load_fcn_doc(self, queries_file):
        parsed = load_queries(queries_file)
        fcn = parsed[0][2]
        assert fcn.__doc__ == 'testing the sqlpi module pls work\nsecond line comment'

    def test_load_fcn_querystring_fmt(self, queries_file):
        parsed = load_queries(queries_file)
        fcn = parsed[0][2]
        assert fcn.__query__ == """select *
-- comment in middle
from public.actor
limit 1;"""


class TestQuery:
    def test_query(self, queries_file):
        sql = Queries(queries_file)
        assert isinstance(sql, Queries)

    def test_query_repr(self, queries_file):
        sql = Queries(queries_file)
        assert 'sqlpy.Queries(' in sql.__repr__()

    def test_query_fcn(self, queries_file):
        sql = Queries(queries_file)
        assert isinstance(sql.TEST_SELECT, functools.partial)

    def test_query_fcn_args(self, queries_file):
        sql = Queries(queries_file)
        assert len(sql.TEST_SELECT.args) == 1


@pytest.mark.usefixtures("enable_logging")
class TestInitLogging:
    def test_logging(self, queries_file, caplog):
        caplog.set_level(logging.DEBUG)
        Queries(queries_file)
        for record in caplog.records:
            assert record.levelname == 'INFO'
        assert 'Found and loaded' in caplog.text


class TestExceptions:
    def test_load_exception(self, invalid_file_path):
        exc_msg = "[Errno No such file or directory] Could not find file: '{}'"\
                  .format(invalid_file_path)
        with pytest.raises(SQLLoadException, message=exc_msg):
            load_queries(invalid_file_path)

    def test_parse_exception(self, invalid_sql_name_start):
        exc_msg = r'^Query does not start with "-- name:": .*'
        with pytest.raises(SQLParseException, match=exc_msg):
            parse_sql_entry(invalid_sql_name_start)

    def test_parse_exception2(self, invalid_sql_name_spaces):
        exc_msg = r'^Query name has spaces: .*'
        with pytest.raises(SQLParseException, match=exc_msg):
            parse_sql_entry(invalid_sql_name_spaces)

    def test_parse_exception3(self, invalid_sql_built):
        exc_msg = r'^parse error, no argument found between \(\.\.\.\): .*'
        with pytest.raises(SQLParseException, match=exc_msg):
            parse_sql_entry(invalid_sql_built)

    def test_parse_exception4(self, invalid_sql_built_args):
        exc_msg = r'^parse error, arg numbers do not match in string s: .*'
        with pytest.raises(SQLParseException, match=exc_msg):
            parse_sql_entry(invalid_sql_built_args)


class TestQueryTypes:
    def test_type_bang(self, sql_bang):
        name, sql_type, fcn = parse_sql_entry(sql_bang)
        assert sql_type == QueryType.INSERT_UPDATE_DELETE

    def test_type_bang_return(self, sql_bang_return):
        name, sql_type, fcn = parse_sql_entry(sql_bang_return)
        assert sql_type == QueryType.RETURN_ID

    def test_type_built(self, sql_built):
        name, sql_type, fcn = parse_sql_entry(sql_built)
        assert sql_type == QueryType.SELECT_BUILT

    def test_type_proc(self, sql_proc):
        name, sql_type, fcn = parse_sql_entry(sql_proc)
        assert sql_type == QueryType.CALL_PROC


@pytest.mark.skipif('TRAVIS' not in os.environ, reason="test data only in Travis")
@pytest.mark.usefixtures("enable_logging")
class TestExec:
    def test_select_1(self, db_cur, sql_select_1):
        name, sql_type, fcn = parse_sql_entry(sql_select_1)
        output = fcn(db_cur, n=1)
        assert output[0] == 1

    def test_select_2(self, db_cur, queries_file):
        sql = Queries(queries_file)
        output = sql.TEST_SELECT(db_cur, n=1)
        assert output[0] == 1

    def test_select_3(self, db_cur, queries_file_glob):
        sql = Queries(queries_file_glob)
        output = sql.TEST_SELECT_B(db_cur, n=1)
        assert output[0] == 1

    def test_select_4(self, db_cur, queries_file_glob):
        sql = Queries(queries_file_glob, uppercase_name=False)
        output = sql.test_select_b(db_cur, n=1)
        assert output[0] == 1

    def test_data1(self, db_cur, queries_file):
        sql = Queries(queries_file)
        data = ('BEN',)
        output = sql.GET_ACTORS_BY_FIRST_NAME(db_cur, data, n=1)
        assert output[0] == 83

    def test_data1_1(self, db_cur, queries_file):
        sql = Queries(queries_file)
        data = ('BEN',)
        output = sql.GET_ACTORS_BY_FIRST_NAME(db_cur, data)
        assert len(output) == 2

    def test_data1_2(self, db_cur, queries_file, caplog):
        caplog.set_level(logging.DEBUG)
        sql = Queries(queries_file, log_query_params=False)
        data = ('BEN',)
        sql.GET_ACTORS_BY_FIRST_NAME(db_cur, data, n=1)
        assert "INFO Arguments: ('BEN',)" not in caplog.text

    def test_data1_3(self, db_cur, queries_file, caplog):
        caplog.set_level(logging.DEBUG)
        sql = Queries(queries_file)
        data = ('BEN',)
        sql.GET_ACTORS_BY_FIRST_NAME(db_cur, data, n=1)
        assert "INFO Arguments: ('BEN',)" in caplog.text

    def test_data2(self, db_cur, queries_file, caplog):
        caplog.set_level(logging.DEBUG)
        sql = Queries(queries_file)
        data = ('Jeff', 'Goldblum')
        sql.PRE_CLEAR_ACTOR(db_cur, data)
        output = sql.INSERT_ACTOR(db_cur, data, n=1)
        assert output == ('Jeff', 'Goldblum')
        assert "('Jeff', 'Goldblum')" in caplog.text

    def test_data2_1(self, db_cur, queries_file):
        sql = Queries(queries_file)
        data = ('Jeff', 'Goldblum')
        output = sql.INSERT_ACTOR(db_cur, data)
        assert output == [('Jeff', 'Goldblum')]

    def test_data2_2(self, db_cur, queries_file):
        sql = Queries(queries_file)
        data = (('Jeff', 'Goldblum'), ('Jeff', 'Goldblum'))
        sql.DELETE_ACTORS(db_cur, data[0])
        output = sql.INSERT_ACTORS(db_cur, data, many=True)
        assert output == [('Jeff', 'Goldblum'), ('Jeff', 'Goldblum')]

    def test_data2_3(self, db_cur, queries_file):
        sql = Queries(queries_file)
        data = (('Jeff', 'Goldblum'), ('Jeff', 'Goldblum'))
        sql.DELETE_ACTORS(db_cur, data[0])
        output = sql.INSERT_ACTORS(db_cur, data, many=True, n=1)
        assert output == ('Jeff', 'Goldblum')

    def test_data2_4(self, db_cur, queries_file):
        sql = Queries(queries_file)
        data = (('Jeff', 'Goldblum'), ('Jeff', 'Goldblum'))
        sql.DELETE_ACTORS(db_cur, data[0])
        output = sql.INSERT_ACTORS(db_cur, data, many=True, n=2)
        assert output == [('Jeff', 'Goldblum'), ('Jeff', 'Goldblum')]

    def test_data3(self, db_cur, queries_file):
        sql = Queries(queries_file)
        kwdata = {
            'country': 'MARS'
        }
        output1 = sql.INSERT_COUNTRY(db_cur, kwdata)
        output2 = sql.DELETE_COUNTRY(db_cur, kwdata)
        assert output1 and output2

    def test_data4(self, db_cur, queries_file, caplog):
        caplog.set_level(logging.DEBUG)
        sql = Queries(queries_file)
        kwdata = {
            'countires': ['United States'],
            'extra_name': 'BEN'
        }
        output = sql.CUSTOMERS_OR_STAFF_IN_COUNTRY(db_cur, kwdata)
        assert len(output) == 37
        assert "'countires': ['United States']" in caplog.text

    def test_data4_1(self, db_cur, queries_file):
        sql = Queries(queries_file)
        kwdata = {
            'countires': ['United States'],
            'extra_name': 'BEN',
            'unmatched_arg_trigger': True
        }
        output = sql.CUSTOMERS_OR_STAFF_IN_COUNTRY(db_cur, kwdata)
        assert len(output) == 37

    def test_data5(self, db_cur, queries_file):
        sql = Queries(queries_file)
        kwdata = {
            'countires': ['United States'],
            'extra_name': 'BEN'
        }
        output = sql.CUSTOMERS_OR_STAFF_IN_COUNTRY(db_cur, kwdata, n=1)
        assert len(output) == 3

    def test_data5_1(self, db_cur, queries_file):
        exc_msg = r'^Named argument supplied which does not match a SQL clause: .*'
        with pytest.raises(SQLArgumentException, match=exc_msg):
            sql = Queries(queries_file, strict_parse=True)
            kwdata = {
                'countires': ['United States'],
                'extra_name': 'BEN',
                'extra_param': 'I should not be here'
            }
            sql.CUSTOMERS_OR_STAFF_IN_COUNTRY(db_cur, kwdata, n=1)

    def test_data5_2(self, db_cur, queries_file):
        sql = Queries(queries_file)
        kwdata = {
            'countires': ['United States'],
            'extra_name': 'BEN'
        }
        output = sql.CUSTOMERS_OR_STAFF_IN_COUNTRY(db_cur, kwdata, n=3)
        assert len(output) == 3

    def test_data6(self, db_cur, queries_file):
        sql = Queries(queries_file)
        kwdata = {
            'countires': ['United States'],
            'extra_name': 'BEN'
        }
        identifiers = ('country',)
        output = sql.CUSTOMERS_OR_STAFF_IN_COUNTRY_SORT(db_cur, kwdata, n=1, identifiers=identifiers)
        assert output == ('BEN', 'EASTER', 'Russian Federation')

    def test_data6_1(self, db_cur, queries_file):
        sql = Queries(queries_file)
        kwdata = {
            'countires': ['United States'],
            'extra_name': 'BEN'
        }
        identifiers = {'order_group': ('country', 'last_name')}
        output = sql.CUSTOMERS_OR_STAFF_IN_COUNTRY_SORT_GROUP(db_cur, kwdata, n=1, identifiers=identifiers)
        assert output == ('BEN', 'EASTER', 'Russian Federation')

    def test_data6_2(self, db_cur, queries_file):
        sql = Queries(queries_file)
        kwdata = {
            'countires': ['United States'],
            'extra_name': 'BEN'
        }
        identifiers = {'order_group': 'country'}
        output = sql.CUSTOMERS_OR_STAFF_IN_COUNTRY_SORT_GROUP(db_cur, kwdata, n=1, identifiers=identifiers)
        assert output == ('BEN', 'EASTER', 'Russian Federation')

    def test_proc1(self, db_cur, queries_file):
        sql = Queries(queries_file)
        output = sql.INVENTORY_CHECK(db_cur, (1, 1))
        assert output == [(1,), (2,), (3,), (4,)] or [(4,), (3,), (2,), (1,)]

    def test_proc1_1(self, db_cur, queries_file):
        sql = Queries(queries_file)
        output = sql.INVENTORY_CHECK(db_cur, (1, 1), n=1)
        assert output == (1,) or (4,)

    def test_proc1_2(self, db_cur, queries_file):
        sql = Queries(queries_file)
        output = sql.INVENTORY_CHECK(db_cur, (1, 1), n=4)
        assert output == [(1,), (2,), (3,), (4,)] or [(4,), (3,), (2,), (1,)]


@pytest.mark.skipif('TRAVIS' not in os.environ, reason="test data only in Travis")
@pytest.mark.usefixtures("enable_logging")
class TestExecExcept:
    def test_data1(self, db_cur, queries_file):
        with pytest.raises(psycopg2.Error):
            sql = Queries(queries_file)
            data = ('BEN',)
            sql.GET_ACTORS_BY_FIRST_NAME_EXP(db_cur, data, n=1)

    def test_data1_1(self, db_cur, queries_file):
        with pytest.raises(psycopg2.Error):
            sql = Queries(queries_file)
            data = ('BEN',)
            sql.GET_ACTORS_BY_FIRST_NAME_EXP(db_cur, data)

    def test_data2(self, db_cur, queries_file):
        with pytest.raises(psycopg2.Error):
            sql = Queries(queries_file)
            data = ('Jeff', 'Goldblum', 'Jeff', 'Goldblum')
            sql.INSERT_ACTOR_EXP(db_cur, data)

    def test_data3(self, db_cur, queries_file):
        with pytest.raises(psycopg2.Error):
            sql = Queries(queries_file)
            kwdata = {
                'country': 'MARS'
            }
            sql.INSERT_COUNTRY_EXP(db_cur, kwdata)
            sql.DELETE_COUNTRY_EXP(db_cur, kwdata)

    def test_data4(self, db_cur, queries_file):
        with pytest.raises(psycopg2.Error):
            sql = Queries(queries_file)
            kwdata = {
                'countires': ['United States'],
                'extra_name': 'BEN'
            }
            sql.CUSTOMERS_OR_STAFF_IN_COUNTRY_EXP(db_cur, kwdata)

    def test_data5(self, db_cur, queries_file):
        with pytest.raises(psycopg2.Error):
            sql = Queries(queries_file, strict_parse=True)
            kwdata = {
                'countires': ['United States'],
                'extra_name': 'BEN'
            }
            sql.CUSTOMERS_OR_STAFF_IN_COUNTRY_EXP(db_cur, kwdata, n=1)

    def test_data6(self, db_cur, queries_file):
        with pytest.raises(psycopg2.Error):
            sql = Queries(queries_file)
            kwdata = {
                'countires': ['United States'],
                'extra_name': 'BEN'
            }
            identifiers = ('country',)
            sql.CUSTOMERS_OR_STAFF_IN_COUNTRY_SORT_EXP(db_cur, kwdata, n=1, identifiers=identifiers)

    def test_data6_1(self, db_cur, queries_file):
        with pytest.raises(SQLParseException):
            sql = Queries(queries_file)
            kwdata = {
                'countires': ['United States'],
                'extra_name': 'BEN'
            }
            identifiers = 'country'
            sql.CUSTOMERS_OR_STAFF_IN_COUNTRY_SORT_GROUP(db_cur, kwdata, n=1, identifiers=identifiers)

    def test_data7(self, db_cur, queries_file):
        with pytest.raises(SQLpyException):
            sql = Queries(queries_file)
            data = ('BEN',)
            sql.GET_ACTORS_BY_FIRST_NAME(db_cur, data, n='1')

    def test_data7_1(self, db_cur, queries_file):
        with pytest.raises(SQLpyException):
            sql = Queries(queries_file)
            data = ('BEN',)
            sql.GET_ACTORS_BY_FIRST_NAME(db_cur, data, n='0')

    def test_data7_2(self, db_cur, queries_file):
        with pytest.raises(SQLpyException):
            sql = Queries(queries_file)
            data = ('BEN',)
            sql.GET_ACTORS_BY_FIRST_NAME(db_cur, data, n=-1)

    def test_data8(self, db_cur, queries_file):
        with pytest.raises(psycopg2.Error):
            sql = Queries(queries_file)
            data = (1, 1)
            sql.INVENTORY_CHECK_EXP(db_cur, data)

    def test_data9(self, db_cur, queries_file):
        with pytest.raises(SQLpyException):
            sql = Queries(queries_file)
            data = (('Jeff', 'Goldblum'), ('Jeff', 'Goldblum'))
            output = sql.INSERT_ACTORS(db_cur, data, many=True, n='2')
            assert output == [('Jeff', 'Goldblum'), ('Jeff', 'Goldblum')]

    def test_data10(self, db_cur, queries_file):
        with pytest.raises(SQLpyException):
            sql = Queries(queries_file)
            kwdata = (['United States'], 'BEN')
            output = sql.CUSTOMERS_OR_STAFF_IN_COUNTRY(db_cur, kwdata)
            assert len(output) == 37
