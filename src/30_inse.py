#! /usr/bin/env python3

# -----------------------------------------------------------------------------
#
# 30_inse.py : parse resources and insert into DATABASE
# 
# -----------------------------------------------------------------------------

import os
import logging
import xml.dom.minidom as md
import pprint
import datetime as dt
import sqlite3

DATABASE        = "data-oasis-atl-apnode-all.db"
CWD             = os.path.abspath(os.path.curdir)
XML_DIR         = os.path.join(CWD, "xml")
DB_DIR          = os.path.join(os.path.curdir, "db")
DB_MANIFEST     = os.path.join(DB_DIR, "inserted.txt")

# -----------------------------------------------------------------------------
# resource name
# -----------------------------------------------------------------------------
RESOURCE_NAME           = "data-oasis-atl-apnode-all"
NS                      = "http://www.caiso.com/soa/OASISReport_v1.xsd"

SQL_DDL         ="""
CREATE TABLE IF NOT EXISTS
    oasis ( 
        timedate                 STRING,
        timedate_posix           INTEGER,
        source                   STRING,
        version                  STRING,
        name                     STRING,
        system                   STRING,
        tz                       STRING,
        report                   STRING,
        apnode_name              STRING,
        apnode_type              STRING,
        start_date               STRING,
        end_date                 STRING,
        start_date_gmt           STRING,
        start_date_posix         INTEGER,
        end_date_gmt             STRING,
        end_date_posix           INTEGER,
        cb_node_flag             STRING,
        max_cb_mw                NUMBER,
        PRIMARY KEY (
                        timedate_posix         ,
                        source                 ,
                        name                   ,
                        system                 ,
                        tz                     ,
                        report                 ,
                        apnode_name            ,
                        apnode_type            ,
                        start_date_posix       ,
                        end_date_posix         ,
                        cb_node_flag     
                    )
        );
"""

INSERT_SQL      ="""
INSERT INTO oasis (
        timedate                  ,
        timedate_posix            ,
        source                    ,
        version                   ,
        name                      ,
        system                    ,
        tz                        ,
        report                    ,
        apnode_name               ,
        apnode_type               ,
        start_date                ,
        end_date                  ,
        start_date_gmt            ,
        start_date_posix          ,
        end_date_gmt              ,
        end_date_posix            ,
        cb_node_flag              ,
        max_cb_mw                 
        )
VALUES (
        :timedate                  ,
        :timedate_posix            ,
        :source                    ,
        :version                   ,
        :name                      ,
        :system                    ,
        :tz                        ,
        :report                    ,
        :apnode_name               ,
        :apnode_type               ,
        :start_date                ,
        :end_date                  ,
        :start_date_gmt            ,
        :start_date_posix          ,
        :end_date_gmt              ,
        :end_date_posix            ,
        :cb_node_flag              ,
        :max_cb_mw                 
    );
"""

def glob_dir(path, ending):
    with os.scandir(path) as it:
        for entry in it:
            if entry.is_file() and entry.name.lower().endswith(ending.lower()):
                yield(entry.name)

def new_xml_files():
    parsed_file_set = set()
    if os.path.exists(DB_MANIFEST):
        with open(DB_MANIFEST, 'r') as m:
            parsed_file_set = set([l.rstrip() for l in m])
    all_file_set = set(glob_dir(XML_DIR, "xml"))
    new_file_set = all_file_set - parsed_file_set
    logging.info({
        "src":RESOURCE_NAME, 
        "action":"new_xml_files", 
        "new_file_set_count":len(new_file_set), 
        "all_file_set_count": len(all_file_set), 
        "parsed_file_set_count": len(parsed_file_set)})
    return sorted(list(new_file_set))


def parse(xml_files):
    for f in xml_files:
        t = os.path.join(XML_DIR, f)
        try:
            yield (f, parse_file(t))
        except Exception as e:
            logging.error({
                "src":RESOURCE_NAME, 
                "action":"parse_file",
                "error":e,
                "file":f,
                "msg":"failed to parse file"
                })

def parse_file(xml_file):
    dom     = md.parse(xml_file)
    header  = get_element("MessageHeader",  dom)
    payload = get_element("MessagePayload", dom)
    rto     = get_element("RTO",            payload)
    name    = get_element("name",           rto)
    items   = get_elements("ATLS_ITEM",    rto)
    return [entry(header, name, item) for item in items] 

def entry(header, name, item):
    return {
        "timedate"                   : value("TimeDate",           header),
        "timedate_posix"             : posix(value("TimeDate",     header)),
        "source"                     : value("Source",             header),
        "version"                    : value("Version",            header),
        "name"                       : value_of(name),
        "system"                     : value("SYSTEM",             item),
        "tz"                         : value("TZ",                 item),
        "report"                     : value("REPORT",             item),
        "apnode_name"                : value("APNODE_NAME",        item),
        "apnode_type"                : value("APNODE_TYPE",        item),
        "start_date"                 : value("START_DATE",         item),
        "end_date"                   : value("END_DATE",           item),
        "start_date_gmt"             : value("START_DATE_GMT",     item),
        "start_date_posix"           : posix(value("START_DATE_GMT", item)),
        "end_date_gmt"               : value("END_DATE_GMT",       item),
        "end_date_posix"             : posix(value("END_DATE_GMT", item)),
        "cb_node_flag"               : value("CB_NODE_FLAG",       item),
        "max_cb_mw"                  : nullable_float("MAX_CB_MW", item)
            }

def date_8601(date):
    return "%s 00:00:00.000" % date

def posix(timestamp):
    try:
        return dt.datetime.fromisoformat(timestamp).timestamp()
    except Exception as e:
        logging.error({
            "src":RESOURCE_NAME, 
            "action":"posix",
            "timestamp":timestamp,
            "error":e,
            "msg":"failed to parse timestamp"
            })
        return -1

class XmlKeyException(Exception):
    pass

def nullable_float(name, dom):
    try:
        return float(value(name, dom))
    except:
        return None

def value(name, dom):
    try:
        return value_of(get_element(name, dom))
    except Exception as e:
        raise XmlKeyException("{'key':%s, 'error':%s}"%(name, e))

def get_element(name, dom):
    try:
        return get_elements(name, dom)[0]
    except Exception as e:
        raise XmlKeyException("{'key':%s, 'error':%s}"%(name, e))

def get_elements(name, dom):
    try:
        e = dom.getElementsByTagName(name)
    except:
        e = dom.getElementsByTagNameNS(NS, name)
    return e

def value_of(node):
    return node.firstChild.nodeValue

def insert(filename_report_tuples, cnx):
    def entry_generator(entries):
        for e in entries:
            yield {
                "timedate":	        e["timedate"],
                "timedate_posix":	e["timedate_posix"],
                "source":		e["source"],
                "version":		e["version"],
                "name":			e["name"],
                "system":		e["system"],
                "tz":			e["tz"],
                "report":		e["report"],
                "apnode_name":		e["apnode_name"],
                "apnode_type":		e["apnode_type"],
                "start_date":	        e["start_date"],
                "end_date":	        e["end_date"],
                "start_date_gmt":	e["start_date_gmt"],
                "start_date_posix":	e["start_date_posix"],
                "end_date_gmt":		e["end_date_gmt"],
                "end_date_posix":	e["end_date_posix"],
                "cb_node_flag":		e["cb_node_flag"],
                "max_cb_mw":		e["max_cb_mw"]
                }
    for (filename, entries) in filename_report_tuples:
        try:
            with cnx:
                cnx.executemany(INSERT_SQL, entry_generator(entries))
#                pp = pprint.PrettyPrinter(indent=4)
#                for genentry in entry_generator(entries):
#                    pp.pprint(genentry) 
#                    cnx.execute(INSERT_SQL, genentry)
            logging.info({
                "src":RESOURCE_NAME, 
                "action":"insert",
                "file":filename,
                "succeeded":len(entries),
                })
            yield filename
        except Exception as ex:
            logging.error({
                "src":RESOURCE_NAME, 
                "action":"insert",
                "error":ex,
                "filename":filename,
                "msg":"insert failed"
                })

def initdb(db_path):
    logging.debug({
        "src":RESOURCE_NAME, 
        "action":"initdb",
        "db_path":db_path
        })
    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute(SQL_DDL)
        conn.commit()
        return conn
    except Exception as e:
        logging.debug({
            "src":RESOURCE_NAME, 
            "action":"initdb",
            "db_path":db_path,
            "error":e,
            "msg":"failed to open database"
            })

def update_manifest(xml_files):
    with open(DB_MANIFEST, 'a') as m:
        for x in xml_files:
            m.write("%s\n" % x)

if __name__ == "__main__":
    logging.basicConfig(format='{"ts":%(asctime)s, "msg":%(message)s}', datefmt='%m/%d/%Y %I:%M:%S %p', level=logging.INFO)
#    pp = pprint.PrettyPrinter(indent=4)
#    [pp.pprint(r) for r in parse(new_xml_files()[:1])]
    try:
        cnx = initdb(os.path.join(DB_DIR, DATABASE))
        update_manifest(insert(parse(new_xml_files()), cnx))
    except:
        cnx.close()
