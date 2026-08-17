from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType

from schemas.chat_models import ChatRequest, ChatResponse
from services.flow.cityhall.contracts import CITYHALL_CONTRACTS
from services.flow.common.state_contract import (
    DetailedGraphContract,
    build_scenario_key,
    complete_detailed_graph,
)
from services.flow.delivery.contracts import DELIVERY_CONTRACTS
from services.flow.professor.absence.response import PROFESSOR_ABSENCE_CONTRACT
from services.flow.professor.appointment.response import PROFESSOR_APPOINTMENT_CONTRACT
from services.flow.professor.assignment.response import PROFESSOR_ASSIGNMENT_CONTRACT
from services.flow.reservation.hair_salon.response import HAIR_SALON_RESERVATION_CONTRACT
from services.flow.reservation.hospital.response import HOSPITAL_RESERVATION_CONTRACT
from services.flow.reservation.restaurant.response import RESTAURANT_RESERVATION_CONTRACT
from services.flow.reservation.study_room.response import STUDY_ROOM_RESERVATION_CONTRACT
from services.flow.scenario.registry import SCENARIOS, ScenarioConfig
from services.flow.scenario.response import complete_scenario_graph_if_supported
from services.flow.support.contracts import SUPPORT_CONTRACTS


class FlowExecutionMode(StrEnum):
    DETAILED = "detailed"
    REGISTERED = "registered"


@dataclass(frozen=True)
class FlowRegistration:
    category: str
    title: str
    mode: FlowExecutionMode
    detailed_contract: DetailedGraphContract | None = None

    @property
    def key(self) -> str:
        return build_scenario_key(self.category, self.title)

    def execute(self, request: ChatRequest) -> ChatResponse:
        if self.mode is FlowExecutionMode.DETAILED:
            if self.detailed_contract is None:
                raise RuntimeError(f"detailed flow contract is missing: {self.key}")
            return complete_detailed_graph(request, self.detailed_contract)

        if self.detailed_contract is not None:
            raise RuntimeError(f"registered flow cannot own a detailed contract: {self.key}")
        response = complete_scenario_graph_if_supported(request)
        if response is None:
            raise RuntimeError(f"registered scenario configuration is missing: {self.key}")
        return response


DETAILED_GRAPH_CONTRACTS: tuple[DetailedGraphContract, ...] = (
    HOSPITAL_RESERVATION_CONTRACT,
    RESTAURANT_RESERVATION_CONTRACT,
    HAIR_SALON_RESERVATION_CONTRACT,
    STUDY_ROOM_RESERVATION_CONTRACT,
    PROFESSOR_APPOINTMENT_CONTRACT,
    PROFESSOR_ASSIGNMENT_CONTRACT,
    PROFESSOR_ABSENCE_CONTRACT,
    *DELIVERY_CONTRACTS,
    *CITYHALL_CONTRACTS,
    *SUPPORT_CONTRACTS,
)


def _detailed_registration(contract: DetailedGraphContract) -> FlowRegistration:
    return FlowRegistration(
        category=contract.category,
        title=contract.title,
        mode=FlowExecutionMode.DETAILED,
        detailed_contract=contract,
    )


def _registered_registration(config: ScenarioConfig) -> FlowRegistration:
    return FlowRegistration(
        category=config.category,
        title=config.title,
        mode=FlowExecutionMode.REGISTERED,
    )


def _build_flow_registry() -> Mapping[str, FlowRegistration]:
    registrations = (
        *(_detailed_registration(contract) for contract in DETAILED_GRAPH_CONTRACTS),
        *(_registered_registration(config) for config in SCENARIOS.values()),
    )
    registry: dict[str, FlowRegistration] = {}
    for registration in registrations:
        if registration.key in registry:
            raise RuntimeError(f"duplicate LangGraph scenario registration: {registration.key}")
        registry[registration.key] = registration
    return MappingProxyType(registry)


FLOW_REGISTRY = _build_flow_registry()


def get_flow_registration(category: str, title: str) -> FlowRegistration | None:
    return FLOW_REGISTRY.get(build_scenario_key(category, title))


def complete_graph_if_supported(request: ChatRequest) -> ChatResponse | None:
    registration = get_flow_registration(request.category, request.title)
    if registration is None:
        return None
    return registration.execute(request)
