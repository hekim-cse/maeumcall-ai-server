from __future__ import annotations


def build_professor_assignment_response(conversation_state: str, state: dict) -> str:
    professor_name = state.get("professor_name") or "교수님"
    course_name = state.get("course_name") or "수업"
    topic = state.get("assignment_topic") or "과제 관련 내용"
    if conversation_state == "collecting_assignment_info":
        missing = state.get("missing_fields") or []
        if "course_name" in missing:
            return (
                f"네, {professor_name}입니다. 어떤 수업의 과제에 관한 문의인지 말씀해주시겠습니까?"
            )
        if "assignment_topic" in missing:
            return f"{course_name} 수업의 어떤 과제와 관련된 문의인지 말씀해주시겠습니까?"
        if "question" in missing:
            return f"{topic} 관련 문의로 확인했습니다. 구체적으로 어떤 부분이 궁금한지 말씀해주시겠습니까?"
        if "user_name" in missing:
            return f"{topic} 관련 문의 내용은 확인했습니다. 성함을 말씀해주시겠습니까?"
        return _answer(state)
    if conversation_state == "answering_assignment_question":
        return _answer(state)
    if conversation_state == "closing":
        return "네, 확인했습니다. 추가로 궁금한 점이 있으면 다시 말씀하시기 바랍니다."
    if conversation_state == "END":
        return "네, 알겠습니다."
    raise ValueError(f"unsupported professor assignment state: {conversation_state}")


def _answer(state: dict) -> str:
    return (
        f"{state.get('user_name') or '학생'} 학생, {state.get('course_name') or '수업'}의 "
        f"{state.get('assignment_topic') or '과제'} 관련 문의로 확인했습니다. "
        "해당 내용은 수업 공지 기준을 먼저 확인하고, 필요한 경우 다시 안내하겠습니다."
    )
