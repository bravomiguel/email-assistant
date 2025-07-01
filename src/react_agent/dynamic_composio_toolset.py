import logging  
import typing as t  
from langchain_core.tools import StructuredTool  
from langgraph.config import get_config  
from composio_langgraph import ComposioToolSet as BaseComposioToolSet  
from composio.utils.shared import json_schema_to_model  
  
logger = logging.getLogger(__name__)  
  
class DynamicComposioToolSet(  
    BaseComposioToolSet,  
    runtime="langgraph_dynamic",  
    description_char_limit=1024,  
    action_name_char_limit=64,  
):  
    """  
    Dynamic Composio toolset that extracts entity_id from LangGraph config at runtime.  
    No need to specify entityId during instantiation.  
    """  
      
    def __init__(self, **kwargs):  
        # Remove entityId from kwargs if present to avoid conflicts  
        kwargs.pop('entityId', None)  
        kwargs.pop('entity_id', None)  
          
        # Log initialization parameters  
        logger.info(f"Initializing DynamicComposioToolSet with: {kwargs}")  
          
        # Initialize with default entity_id - will be overridden dynamically  
        super().__init__(entity_id="default", **kwargs)  
          
        logger.info(f"Base entity_id set to: {self.entity_id}")  
      
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
                dynamic_entity_id = configurable.get("user_id")  
                  
                # Fallback hierarchy: config user_id -> method param -> toolset default  
                final_entity_id = dynamic_entity_id or entity_id or self.entity_id  
                  
                # Comprehensive logging  
                logger.info("=" * 50)  
                logger.info(f"EXECUTING ACTION: {action}")  
                logger.info(f"LangGraph config available: {config is not None}")
                logger.info(f"user_id from config: {dynamic_entity_id}")  
                # logger.info(f"Method entity_id param: {entity_id}")  
                # logger.info(f"Toolset default entity_id: {self.entity_id}")  
                logger.info(f"FINAL entity_id: {final_entity_id}")  
                logger.info("=" * 50)  
                  
            except RuntimeError as e:  
                final_entity_id = entity_id or self.entity_id  
                logger.warning(f"RuntimeError getting LangGraph config: {e}")  
                logger.info(f"Using fallback entity_id: {final_entity_id}")  
  
            return self.execute_action(  
                action=action,  
                params=kwargs,  
                entity_id=final_entity_id,  
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
  
# Now you can instantiate without entityId  
toolset = DynamicComposioToolSet()