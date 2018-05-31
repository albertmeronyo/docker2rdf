#!/usr/bin/env python

# docker2rdf.py: Mapper to represent Dockerfiles as RDF triples

from dockerfile_parse import DockerfileParser
import sys
from rdflib import Graph, RDF, URIRef, Namespace, Literal, RDFS
import hashlib
import urllib
from itertools import groupby

import static

class docker2rdf(object):
    def __init__(self):
        # Initialize the RDF graph
        self.g = Graph()

        dckr_uri = URIRef("http://purl.org/dckr/vocab#")
        prov_uri = URIRef("http://www.w3.org/ns/prov#")
        foaf_uri = URIRef("http://xmlns.com/foaf/0.1/")
        d_uri = URIRef("http://purl.org/dckr/resource/")
        self.dckr = Namespace(dckr_uri)
        self.prov = Namespace(prov_uri)
        self.foaf = Namespace(foaf_uri)
        self.d = Namespace(d_uri)

        self.g.bind('dckr', self.dckr)
        self.g.bind('prov', self.prov)
        self.g.bind('foaf', self.foaf)
        self.g.bind('d', self.d)

    def parse(self, dockerfile):
        # Parse the Dockerfile
        with open(dockerfile, 'r') as infile:
            dockercontent = infile.read()

        self.dfp = DockerfileParser()
        self.dfp.content = dockercontent

    def semanticize(self):

        for entry in self.dfp.structure:
            instr = entry['instruction']
            val = entry['value']
            cnt = entry['content']
            if instr == 'FROM':
                img1_uri = self.d[urllib.quote("image/" + val)]
                self.g.add((img1_uri, RDF.type, self.prov['Entity']))
                self.g.add((img1_uri, RDF.type, self.dckr['DockerImage']))
                self.g.add((img1_uri, self.dckr.repo, Literal(val.split(':')[0])))
                if len(val.split(':')) > 1:
                    self.g.add((img1_uri, self.dckr.tag, Literal(val.split(':')[1])))


        lastimg_uri = img1_uri
        step_cnt = 1
        for entry in self.dfp.structure:
            instr = entry['instruction']
            val = entry['value']
            cnt = entry['content']
            # Create Activity (step)
            step_uri = self.d["step/" + hashlib.md5(cnt).hexdigest()]
            self.g.add((step_uri, RDF.type, self.prov['Activity']))
            self.g.add((step_uri, self.prov.used, lastimg_uri))
            self.g.add((step_uri, RDFS.label, Literal(cnt)))
            self.g.add((step_uri, self.dckr.order, Literal(step_cnt)))
            if instr == 'MAINTAINER':
                mnt_id = hashlib.md5(val).hexdigest()
                self.g.add((self.d[mnt_id], RDF.type, self.foaf['Person']))
                self.g.add((self.d[mnt_id], RDF.type, self.prov['Agent']))
                self.g.add((self.d[mnt_id], self.foaf.mbox, Literal(val)))
            elif instr == 'RUN':
                # Check for use of APT
                if 'apt-get' in val.split():
                    packages = self.apt_cleanup(val.split())
                    for p in packages:
                        pkg_uri = self.d["package/apt/" + p]
                        self.g.add((pkg_uri, RDF.type, self.dckr['DebianPackage']))
                        self.g.add((pkg_uri, RDF.type, self.prov['Entity']))
                        self.g.add((pkg_uri, RDFS.label, Literal(p)))
                        self.g.add((step_uri, self.prov.used, pkg_uri))

            # Create output image
            img_uri = self.d["image/" + hashlib.md5(cnt).hexdigest()]
            self.g.add((img_uri, RDF.type, self.prov['Entity']))
            self.g.add((img_uri, RDF.type, self.dckr['DockerImage']))
            self.g.add((img_uri, self.prov.wasGeneratedBy, step_uri))
            self.g.add((img_uri, self.prov.wasDerivedFrom, lastimg_uri))

            lastimg_uri = img_uri
            step_cnt += 1

        # Last image is attributed to MAINTAINER
        self.g.add((lastimg_uri, self.prov.wasAttributedTo, self.d[mnt_id]))

    def serialize(self):
        # Output graph
        return self.g.serialize(format='ntriples')

    def apt_cleanup(self, run_list):
        # groupby(l, lambda x: x == "&&")

        p = [list(group) for k, group in groupby(run_list, lambda x: x == "&&") if not k]
        q = []
        for l in p:
            if 'apt-get' in l:
                for el in l:
                    if el not in static.APT_DISCARDS:
                        q.append(el)

        return q

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print "Usage: ./docker2rdf.py <Dockerfile>"
        exit(0)

    d2r = docker2rdf()
    d2r.parse(sys.argv[1])
    d2r.semanticize()
    print d2r.serialize()

    exit(0)
