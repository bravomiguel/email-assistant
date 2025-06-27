import typing as t
from langchain_core.tools import StructuredTool
from langgraph.config import get_config
from composio_langgraph import ComposioToolSet as BaseComposioToolSet
from composio.utils.shared import json_schema_to_model


class DynamicEntityComposioToolSet(BaseComposioToolSet):
    def _wrap_tool(
        self,
        schema: t.Dict[str, t.Any],
        entity_id: t.Optional[str] = None,
        skip_default: bool = False,
    ) -> StructuredTool:
        """Wraps composio tool with LangGraph config support for dynamic entity_id."""
        action = schema["name"]
        description = schema["description"]
        schema_params = schema["parameters"]

        def execute_with_dynamic_entity(**kwargs) -> t.Dict:
            """Execute action with dynamic entity_id from LangGraph config."""
            try:
                config = get_config()
                configurable = config.get("configurable", {}) if config else {}
                dynamic_entity_id = configurable.get(
                    "user_id", entity_id or self.entity_id
                )
            except RuntimeError:
                dynamic_entity_id = entity_id or self.entity_id

            return self.execute_action(
                action=action,
                params=kwargs,
                entity_id=dynamic_entity_id,
                _check_requested_actions=True,
            )

        parameters = json_schema_to_model(
            json_schema=schema_params,
            skip_default=skip_default,
        )

        tool = StructuredTool.from_function(
            name=action,
            description=description,
            args_schema=parameters,
            return_schema=True,
            func=execute_with_dynamic_entity,
            handle_tool_error=True,
            handle_validation_error=True,
        )
        return tool
