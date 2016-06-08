import logging
logger = logging.getLogger(__name__)

import restful
import api.handlers.ws_domains as ws_domains
import api
import hashlib
import os
import re
import sys

import api.jsonh

import pprint

from subprocess import *

class RawDomain(object):

    def __init__(self):
        print "Raw.__init__"

    @staticmethod
    def createNode(node_type, name):
		return {
			't': node_type,
			'n': name
			}

    @staticmethod
    def createLink(source, target):
        return {
            's': source,
            't': target
            }

    @staticmethod
    def nodesFromRules(rules, policyid, nodeMap, linkMap, nodeList, linkList):
    	for r in rules:
            new_subject_node = new_object_node = new_class_node = new_perm_node = None

            r['policy'] = policyid

            # Find existing node if it exists
            curr_subject_node = nodeMap.get("subject-" + r['subject'], -1)
            curr_object_node = nodeMap.get("object-" + r['object'], -1)
            curr_class_node = nodeMap.get("class-" + r['class'], -1)
            curr_perm_node = nodeMap.get("perm-" + r['perm'], -1)

            # If node exists then update it, else create a new one
            if curr_subject_node >= 0:
                None
            else:
                nodeMap["subject-" + r['subject']] = len(nodeList)
                new_subject_node = len(nodeList)
                nodeList.append(RawDomain.createNode("s", r['subject']))
            if curr_object_node >= 0:
                None
            else:
                nodeMap["object-" + r['object']] = len(nodeList)
                new_object_node = len(nodeList)
                nodeList.append(RawDomain.createNode("o", r['object']))
            if curr_class_node >= 0:
                None
            else:
                nodeMap["class-" + r['class']] = len(nodeList)
                new_class_node = len(nodeList)
                nodeList.append(RawDomain.createNode("c", r['class']))
            if curr_perm_node >= 0:
                None
            else:
                nodeMap["perm-" + r['perm']] = len(nodeList)
                new_perm_node = len(nodeList)
                nodeList.append(RawDomain.createNode("p", r['perm']))

            RawDomain.generateLink(curr_perm_node, curr_object_node, new_perm_node, new_object_node, nodeList, linkMap, linkList, r, policyid)
            RawDomain.generateLink(curr_subject_node, curr_perm_node, new_subject_node, new_perm_node, nodeList, linkMap, linkList, r, policyid)
            RawDomain.generateLink(curr_object_node, curr_class_node, new_object_node, new_class_node, nodeList, linkMap, linkList, r, policyid)
            RawDomain.generateLink(curr_perm_node, curr_class_node, new_perm_node, new_class_node, nodeList, linkMap, linkList, r, policyid)

    @staticmethod
    def generateLink(curr_source_node, curr_target_node, new_source_node, new_target_node, nodeList, linkMap, linkList, r, policyid):
        if curr_source_node >= 0 and curr_target_node == -1:
            source = curr_source_node
            target = new_target_node
            s_node = nodeList[source]
            t_node = nodeList[target]
            link = RawDomain.createLink(source, target)
            linkMap[s_node['t'] + '-' + s_node['n'] + '-' + t_node['t'] + '-' + t_node['n']] = len(linkList)
            linkList.append(link)
        elif curr_source_node == -1 and curr_target_node >= 0:
            source = new_source_node
            target = curr_target_node
            s_node = nodeList[source]
            t_node = nodeList[target]
            link = RawDomain.createLink(source, target)
            linkMap[s_node['t'] + '-' + s_node['n'] + '-' + t_node['t'] + '-' + t_node['n']] = len(linkList)
            linkList.append(link)
        elif curr_source_node == -1 and not curr_target_node >= 0:
            source = new_source_node
            target = new_target_node
            s_node = nodeList[source]
            t_node = nodeList[target]
            link = RawDomain.createLink(source, target)
            linkMap[s_node['t'] + '-' + s_node['n'] + '-' + t_node['t'] + '-' + t_node['n']] = len(linkList)
            linkList.append(link)
        else:
            source = curr_source_node
            target = curr_target_node
            s_node = nodeList[source]
            t_node = nodeList[target]
            link_key = s_node['t'] + '-' + s_node['n'] + '-' + t_node['t'] + '-' + t_node['n']
            if link_key in linkMap:
                linkIdx = linkMap[link_key]
                link = linkList[linkIdx]
            else:
                link = None

        if link:
            None
        else:
            # Source and target were previously found in two separate rules
            link = RawDomain.createLink(source, target)
            linkMap[s_node['t'] + '-' + s_node['n'] + '-' + t_node['t'] + '-' + t_node['n']] = len(linkList)
            linkList.append(link)

    def fetch_graph(self, msg):
        """ Return JSON for the nodes and links of the raw policy rules.
        """

        # msg.payload.policy is the id
        refpol_id = msg['payload']['policy']
        del msg['payload']['policy']

        refpol_id = api.db.idtype(refpol_id)
        refpol = ws_domains.call('refpolicy', 'Read', refpol_id)

        # If already parsed, just return the one we already translated.
        if (refpol.parsed):
            logger.info("Returning cached JSON")
        else:
            refpol = ws_domains.call('raw', 'parse', msg)

        if (not refpol['parsed']['parameterized']['nodes'] and
            not refpol['parsed']['parameterized']['links']):

            # Build the node and link lists from the rules table
            rules = refpol['parsed']['parameterized']['rules']
            node_map = {}
            link_map = {}
            node_list = []
            link_list = []
            RawDomain.nodesFromRules(rules, refpol.id, node_map, link_map, node_list, link_list)

            # Sparsify/compress the dicts/JSON objects
            node_list = api.jsonh.dumps(node_list)
            link_list = api.jsonh.dumps(link_list)

            refpol['parsed']['parameterized']['nodes'] = node_list
            refpol['parsed']['parameterized']['links'] = link_list

            refpol.Insert()

        # Don't send the rules to the client
        refpol['parsed']['parameterized'].pop('rules', None)

        return {
            'label': msg['response_id'],
            'payload': api.db.json.dumps(refpol.parsed)
        }

    def parse(self, msg):
        """ Given a set of parameters of the form, return the
        JSON for the raw module.
        """

        # msg.payload.policy is the id
        refpol_id = msg['payload']['policy']
        del msg['payload']['policy']

        refpol_id = api.db.idtype(refpol_id)
        refpol = ws_domains.call('refpolicy', 'Read', refpol_id)

        # If already parsed, just return the one we already translated.
        if (refpol.parsed):
            logger.info("Returning cached JSON")

        else:

            table = []

            # Need to get the parsed data for all the modules
            # Use ws_domains.call() to invoke raw.py and get the raw policy
            line_num = 0
            print("----------------------")
            print(len(raw.splitlines()))
            print("----------------------")
            for line in raw.splitlines():
                line_num += 1
                # Split on ":"
                rule = line.strip().split(":")

                lside = rule[0].lstrip("allow").strip()
                rside = rule[1].strip()

                if lside.find("{") == -1:
                    # Should be "subj_t obj_t;"
                    subj_t = lside.split(" ")[0]
                    obj_t = lside.split(" ")[1]
                elif lside.find("{") < lside.find(" "):
                    # We have a list of subjects
                    subj_t = lside[lside.find("{")+1:lside.find("}")].strip()
                    if lside.find("}") == lside.rfind("}"):
                        # {subj_t1 subj_t2} obj_t;
                        obj_t = lside.split("}")[1].rstrip(";").strip()
                    else:
                        # {subj_t1 subj_t2} {obj_t1 obj_t2};
                        obj_t = lside[lside.rfind("{")+1:lside.rfind("}")].strip()
                else:
                    # subj_t {obj_t1 obj_t2};
                    subj_t = lside.split("{")[0].strip()
                    obj_t = lside[lside.find("{")+1:lside.find("}")].strip()

                if rside.find("{") == -1:
                    # Should be "obj_c perm;"
                    obj_c = rside.split(" ")[0]
                    perms = rside.split(" ")[1].rstrip(";")
                elif rside.find("{") < rside.find(" "):
                    # We have a list of classes
                    obj_c = rside[rside.find("{")+1:rside.find("}")].strip()
                    if rside.find("}") == rside.rfind("}"):
                        # {obj_c1 obj_c2} permission;
                        perms = rside.split("}")[1].rstrip(";").strip()
                    else:
                        # {obj_c1 obj_c2} {perm1 perm2};
                        perms = rside[rside.rfind("{")+1:rside.rfind("}")].strip()
                else:
                    # obj_c {perm1 perm2};
                    obj_c = rside.split("{")[0].strip()
                    perms = rside[rside.find("{")+1:rside.find("}")].strip()

                for s in subj_t.split(" "):
                    for ot in obj_t.split(" "):
                        for oc in obj_c.split(" "):
                            for p in perms.split(" "):
                                row = {"subject":s, "object":ot, "class":oc, "perm":p, "rule": line.strip()}
                                table.append(row)

            refpol['parsed'] = {
                'version': '1.0',
                'errors': [],
                'parameterized': {"rules": table}
            }

            print("=====================")
            print("Pre insert")
            print("=====================")

            refpol.Insert()
            print("=====================")
            print("Post insert")
            print("=====================")

        # Don't send the rules to the client
        refpol['parsed']['parameterized'].pop('rules', None)

        return {
            'label': msg['response_id'],
            'payload': api.db.json.dumps(refpol.parsed)
        }

    def translate_selinux(self, params):
        """ Given a set of parameters of the form, return the
        JSON for the raw module.

            {
              "refpolicy": "minimal",
              "modules": [
                { "name": "test",
                  "if": " ... source of .if file ...",
                  "te": " ... source of .te file ...",
                  "fc": " ... source of .fc file ..."
                }
              ]
            }
        """
        
        logger.info("Params: {0}".format(params))
        # output = self._make_request('POST', '/import/selinux',
        #                             params if isinstance(params, basestring) else api.db.json.dumps(params))

        # exec_str = "./ide/tools/te2json.py"
        # exec_str += " -j -t -i"
        # #filename = "~/Documents/V3SPA/ide/tools/" + (params['filename'] if params['filename'] else "apache.te")
        # filename = params['module']['te_file']
        # exec_str += " " + filename
        # output = Popen([exec_str], stdout=PIPE, shell=True).communicate()[0]

        with open(params['module']['te_file'], 'r') as myfile:
            data = myfile.read()

        return {
            "result": data,
            "errors": []
        }

    def handle(self, msg):
        if msg['request'] == 'parse':
            return self.parse(msg)
        elif msg['request'] == 'fetch_graph':
            return self.fetch_graph(msg)
        else:
            raise Exception("Invalid message type for 'raw' domain")


def __instantiate__():
    return RawDomain()

