# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

from abc import abstractmethod
from typing import Callable

import numpy as np

from maro.communication import Proxy, RegisterTable
from maro.rl.agent.abs_agent_manager import AbsAgentManager

from ..common import ActorTrainerComponent, MessageTag, PayloadKey


class Trainer(object):
    """Abstract distributed learner class.

    Args:
        agent_manager (AbsAgentManager): An AgentManager instance that manages all agents.
        experience_collection_func (Callable): Function to collect experiences from multiple remote actors.
        proxy_params: Parameters required for instantiating an internal proxy for communication.
    """

    def __init__(
        self,
        agent_manager: AbsAgentManager,
        experience_collecting_func: Callable,
        **proxy_params
    ):
        super().__init__()
        self._agent_manager = agent_manager
        self._experience_collecting_func = experience_collecting_func
        self._proxy = Proxy(component_type=ActorTrainerComponent.TRAINER.value, **proxy_params)
        self._num_actors = len(self._proxy.peers_name["actor"])
        self._registry_table = RegisterTable(self._proxy.peers_name)
        self._registry_table.register_event_handler(
            f"{ActorTrainerComponent.ACTOR.value}:{MessageTag.UPDATE.value}:{self._num_actors}", self.update
        )

    @abstractmethod
    def update(self, messages):
        raise NotImplementedError

    def dump_models(self, dir_path: str):
        self._agent_manager.dump_models_to_files(dir_path)

    def _collect(self, messages: list):
        for msg in messages:
            self._scheduler.record_performance(msg.payload[PayloadKey.PERFORMANCE])
            self._experiences[msg.source] = msg.payload[PayloadKey.EXPERIENCES]

        self._rollout_complete_counter = len(messages)


class SEEDTrainer(Trainer):
    """Abstract distributed learner class.

    Args:
        agent_manager (AbsAgentManager): An AgentManager instance that manages all agents.
        experience_collection_func (Callable): Function to collect experiences from multiple remote actors.
        proxy_params: Parameters required for instantiating an internal proxy for communication.
    """
    def __init__(
        self,
        agent_manager: AbsAgentManager,
        experience_collecting_func: Callable,
        **proxy_params
    ):
        super().__init__(agent_manager, experience_collecting_func, **proxy_params)
        self._registry_table.register_event_handler(
            f"{ActorTrainerComponent.ACTOR.value}:{MessageTag.CHOOSE_ACTION.value}:{self._num_actors}", self._get_action
        )

    @abstractmethod
    def train(self, experiences):
        raise NotImplementedError

    def _get_action(self, messages: list):
        state_batch = np.vstack([msg.payload[PayloadKey.STATE] for msg in messages])
        agent_id = messages[0].payload[PayloadKey.AGENT_ID]
        model_action_batch = self._agent_manager[agent_id].choose_action(state_batch)
        for msg, model_action in zip(messages, model_action_batch):
            self._proxy.reply(received_message=msg, tag=MessageTag.ACTION, payload={PayloadKey.ACTION: model_action})
