#
# Licensed to the Apache Software Foundation (ASF) under one or more
# contributor license agreements.  See the NOTICE file distributed with
# this work for additional information regarding copyright ownership.
# The ASF licenses this file to You under the Apache License, Version 2.0
# (the "License"); you may not use this file except in compliance with
# the License.  You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

from sklearn.pipeline import Pipeline
import os
import json
import shutil
import uuid

__VERSION__ = "0.5.0-SNAPSHOT"


def serialize_to_bundle(self, path, model_name, init=False):
    serializer = SimpleSparkSerializer()
    serializer.serialize_to_bundle(self, path, model_name, init)


def deserialize_from_bundle(self, path):
    serializer = SimpleSparkSerializer()
    return serializer.deserialize_from_bundle(path)

setattr(Pipeline, 'serialize_to_bundle', serialize_to_bundle)
setattr(Pipeline, 'deserialize_from_bundle', deserialize_from_bundle)
setattr(Pipeline, 'op', 'pipeline')
setattr(Pipeline, 'name', "{}_{}".format('pipeline', uuid.uuid1()))
setattr(Pipeline, 'serializable', True)


class SimpleSparkSerializer(object):
    def __init__(self):
        super(SimpleSparkSerializer, self).__init__()

    def serialize_to_bundle(self, transformer, path, model_name, init=False):

        model_dir = path
        if init:
            # If bundle path already exists, delte it and create a clean directory
            if os.path.exists("{}/{}".format(path, model_name)):
                shutil.rmtree("{}/{}".format(path, model_name))

            model_dir = "{}/{}".format(path, model_name)
            os.mkdir(model_dir)

            # Write Pipeline Bundle file
            with open("{}/{}".format(model_dir, 'bundle.json'), 'w') as outfile:
                json.dump(self.get_bundle(transformer), outfile, indent=3)

        else:
            # Write model file
            with open("{}/{}".format(model_dir, 'model.json'), 'w') as outfile:
                json.dump(self.get_model(transformer), outfile, indent=3)

            # Write node file
            with open("{}/{}".format(model_dir, 'node.json'), 'w') as outfile:
                json.dump(self.get_node(transformer), outfile, indent=3)

        for step in [x[1] for x in transformer.steps if hasattr(x[1], 'serialize_to_bundle')]:
            name = step.name

            if step.op == 'pipeline':
                # Create the node directory
                bundle_dir = "{}/{}.node".format(model_dir, name)
                os.mkdir(bundle_dir)

                # Write model file
                with open("{}/{}".format(bundle_dir, 'model.json'), 'w') as outfile:
                    json.dump(self.get_model(step), outfile, indent=3)

                # Write node file
                with open("{}/{}".format(bundle_dir, 'node.json'), 'w') as outfile:
                    json.dump(self.get_node(step), outfile, indent=3)

                for step_i in [x[1] for x in step.steps]:
                    step_i.serialize_to_bundle(bundle_dir, step_i.name)

            elif step.op == 'feature_union':
                step.serialize_to_bundle(model_dir, step.name)
            else:
                step.serialize_to_bundle(model_dir, step.name)

            if isinstance(step, list):
                pass

    def deserialize_from_bundle(self, path):
        return NotImplementedError

    def get_bundle(self, transformer):
        js = {
          "name": transformer.name,
          "format": "json",
          "version": __VERSION__,
          "nodes": self._extract_nodes(transformer.steps)
        }
        return js

    def get_node(self, transformer):
        js = {
          "name": "feature_pipeline",
          "shape": {
            "inputs": [],
            "outputs": []
          }
        }
        return js

    def get_model(self, transformer):
        js = {
          "op": transformer.op,
          "attributes": [{
            "name": "nodes",
            "type": {
              "type": "list",
              "base": "string"
            },
            "value": self._extract_nodes(transformer.steps)
          }]
        }
        return js

    def _extract_nodes(self, steps):
        pipeline_steps = []
        for name, step in steps:
            if step.op == 'feature_union':
                union_steps = [x[1].name for x in step.transformer_list if hasattr(x[1], 'serialize_to_bundle') and x[1].serializable]
                pipeline_steps += union_steps
            elif hasattr(step, 'serialize_to_bundle') and step.serializable:
                pipeline_steps.append(name)
        return pipeline_steps