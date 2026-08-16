from __future__ import annotations


class AIServiceError(RuntimeError):
    """Base exception for failures that must cross the API boundary explicitly."""

    status_code = 502
    code = "AI_SERVICE_ERROR"
    public_message = "AI 처리 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."


class AIProviderUnavailableError(AIServiceError):
    status_code = 503
    code = "AI_PROVIDER_UNAVAILABLE"
    public_message = "AI 모델을 사용할 수 없습니다. 서버 설정을 확인해 주세요."


class AIProviderExecutionError(AIServiceError):
    code = "AI_PROVIDER_EXECUTION_FAILED"
    public_message = "AI 모델 호출에 실패했습니다. 잠시 후 다시 시도해 주세요."


class AIResponseValidationError(AIServiceError):
    code = "AI_RESPONSE_VALIDATION_FAILED"
    public_message = "AI 응답을 검증하지 못했습니다. 요청을 다시 시도해 주세요."


class PromptConfigurationError(AIServiceError):
    status_code = 500
    code = "PROMPT_CONFIGURATION_ERROR"
    public_message = "시나리오 프롬프트 구성이 올바르지 않습니다."


class ScenarioStateValidationError(AIServiceError):
    status_code = 422
    code = "INVALID_SCENARIO_STATE"
    public_message = "시나리오 상태 형식이 올바르지 않습니다."
