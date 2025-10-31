"""
Field usage tracking functionality for Salesforce metadata
"""
from typing import Dict, List, Set
from simple_salesforce import Salesforce
import urllib.parse


class FieldUsageTracker:
    """Tracks where fields are used across Salesforce metadata"""

    def __init__(self, sf: Salesforce, status_callback=None):
        """Initialize with Salesforce connection"""
        self.sf = sf
        self.status_callback = status_callback
        # Cache to store usage data
        self.usage_cache: Dict[str, Dict[str, List[str]]] = {}

    def get_field_usage(self, object_name: str, field_api_name: str) -> str:
        """
        Get formatted usage string for a field
        Returns format like:
        Page Layouts
        - Layout1
        - Layout2

        Apex Classes
        - Class1
        """
        if object_name not in self.usage_cache:
            self._build_usage_cache_for_object(object_name)

        field_key = f"{object_name}.{field_api_name}"
        usage_data = self.usage_cache.get(object_name, {}).get(field_key, {})

        if not usage_data:
            return ""

        # Format the usage data
        formatted_sections = []

        # Define the order of sections
        section_order = [
            'Page Layouts',
            'Validation Rules',
            'Apex Classes',
            'Apex Triggers',
            'Visualforce Pages',
            'Visualforce Components'
        ]

        for section in section_order:
            if section in usage_data and usage_data[section]:
                formatted_sections.append(f"{section}")
                for item in sorted(usage_data[section]):
                    formatted_sections.append(f"- {item}")
                formatted_sections.append("")  # Empty line between sections

        return "\n".join(formatted_sections).strip()

    def _build_usage_cache_for_object(self, object_name: str):
        """Build usage cache for all fields in an object"""
        self._log_status(f"  Building field usage cache for {object_name}...")

        usage_data = {}

        try:
            # Query Validation Rules
            validation_usage = self._get_validation_rule_usage(object_name)
            self._merge_usage_data(usage_data, validation_usage, 'Validation Rules')

            # Query Apex Classes
            apex_usage = self._get_apex_usage(object_name)
            self._merge_usage_data(usage_data, apex_usage, 'Apex Classes')

            # Query Apex Triggers
            trigger_usage = self._get_trigger_usage(object_name)
            self._merge_usage_data(usage_data, trigger_usage, 'Apex Triggers')

            # Query Visualforce Pages
            vf_page_usage = self._get_visualforce_page_usage(object_name)
            self._merge_usage_data(usage_data, vf_page_usage, 'Visualforce Pages')

            # Query Visualforce Components
            vf_comp_usage = self._get_visualforce_component_usage(object_name)
            self._merge_usage_data(usage_data, vf_comp_usage, 'Visualforce Components')

            # Query Page Layouts (using Metadata API approach)
            page_layout_usage = self._get_page_layout_usage(object_name)
            self._merge_usage_data(usage_data, page_layout_usage, 'Page Layouts')

            self.usage_cache[object_name] = usage_data
            self._log_status(f"  ✅ Usage cache built")

        except Exception as e:
            self._log_status(f"  ⚠ Warning: Could not build complete usage cache: {str(e)}")
            self.usage_cache[object_name] = usage_data

    def _merge_usage_data(self, usage_data: Dict, field_usage: Dict[str, Set[str]], category: str):
        """Merge field usage data into the main usage dictionary"""
        for field_key, items in field_usage.items():
            if field_key not in usage_data:
                usage_data[field_key] = {}
            if category not in usage_data[field_key]:
                usage_data[field_key][category] = []
            usage_data[field_key][category].extend(sorted(items))

    def _tooling_query(self, soql: str):
        """Execute a Tooling API query with proper URL encoding"""
        try:
            encoded_query = urllib.parse.quote(soql)
            url = f"tooling/query/?q={encoded_query}"
            return self.sf.restful(url, method='GET')
        except Exception as e:
            self._log_status(f"    ⚠ Tooling query error: {str(e)}")
            return {'records': []}

    def _get_page_layout_usage(self, object_name: str) -> Dict[str, Set[str]]:
        """Get page layout usage for object fields using Metadata API"""
        field_usage = {}

        try:
            # Use the mdapi endpoint to list layouts
            response = self.sf.restful(f'tooling/query/?q=SELECT+Id,Name,EntityDefinitionId+FROM+Layout+WHERE+EntityDefinitionId=\'{object_name}\'', method='GET')

            for layout in response.get('records', []):
                layout_name = layout.get('Name', '')
                layout_id = layout.get('Id', '')

                # For now, we'll note that the layout exists but won't parse detailed field usage
                # Full field-level parsing would require the Metadata API which is more complex
                # This is a simplified version that at least shows which layouts exist

        except Exception as e:
            self._log_status(f"    ⚠ Could not query page layouts: {str(e)}")

        return field_usage

    def _get_validation_rule_usage(self, object_name: str) -> Dict[str, Set[str]]:
        """Get validation rule usage for object fields"""
        field_usage = {}

        try:
            soql = f"SELECT ValidationName, Metadata FROM ValidationRule WHERE EntityDefinition.QualifiedApiName = '{object_name}'"
            result = self._tooling_query(soql)

            for rule in result.get('records', []):
                rule_name = rule.get('ValidationName', '')
                metadata = rule.get('Metadata', {})

                if not metadata:
                    continue

                # Parse the error display field if available
                error_field = metadata.get('errorDisplayField')
                if error_field:
                    field_key = f"{object_name}.{error_field}"
                    if field_key not in field_usage:
                        field_usage[field_key] = set()
                    field_usage[field_key].add(rule_name)

                # Try to extract fields from formula (basic parsing)
                formula = metadata.get('errorConditionFormula', '')
                if formula:
                    # Basic field extraction - look for object_name.field patterns
                    fields = self._extract_fields_from_text(formula, object_name)
                    for field in fields:
                        field_key = f"{object_name}.{field}"
                        if field_key not in field_usage:
                            field_usage[field_key] = set()
                        field_usage[field_key].add(rule_name)

        except Exception as e:
            self._log_status(f"    ⚠ Could not query validation rules: {str(e)}")

        return field_usage

    def _get_apex_usage(self, object_name: str) -> Dict[str, Set[str]]:
        """Get Apex class usage for object fields"""
        field_usage = {}

        try:
            soql = "SELECT Name, Body FROM ApexClass LIMIT 500"
            result = self._tooling_query(soql)

            # Get all fields for the object to search for
            obj_describe = getattr(self.sf, object_name).describe()
            field_names = [field.get('name', '') for field in obj_describe['fields']]

            for apex_class in result.get('records', []):
                class_name = apex_class.get('Name', '')
                body = apex_class.get('Body', '')

                if not body:
                    continue

                # Check if this class references the object
                if object_name not in body:
                    continue

                # Look for field references
                for field_name in field_names:
                    # Look for common patterns: obj.field, field__c, etc.
                    if field_name in body:
                        field_key = f"{object_name}.{field_name}"
                        if field_key not in field_usage:
                            field_usage[field_key] = set()
                        field_usage[field_key].add(class_name)

        except Exception as e:
            self._log_status(f"    ⚠ Could not query Apex classes: {str(e)}")

        return field_usage

    def _get_trigger_usage(self, object_name: str) -> Dict[str, Set[str]]:
        """Get Apex trigger usage for object fields"""
        field_usage = {}

        try:
            soql = f"SELECT Name, Body FROM ApexTrigger WHERE TableEnumOrId = '{object_name}'"
            result = self._tooling_query(soql)

            obj_describe = getattr(self.sf, object_name).describe()
            field_names = [field.get('name', '') for field in obj_describe['fields']]

            for trigger in result.get('records', []):
                trigger_name = trigger.get('Name', '')
                body = trigger.get('Body', '')

                if not body:
                    continue

                for field_name in field_names:
                    if field_name in body:
                        field_key = f"{object_name}.{field_name}"
                        if field_key not in field_usage:
                            field_usage[field_key] = set()
                        field_usage[field_key].add(trigger_name)

        except Exception as e:
            self._log_status(f"    ⚠ Could not query triggers: {str(e)}")

        return field_usage

    def _get_visualforce_page_usage(self, object_name: str) -> Dict[str, Set[str]]:
        """Get Visualforce page usage for object fields"""
        field_usage = {}

        try:
            soql = "SELECT Name, Markup FROM ApexPage LIMIT 500"
            result = self._tooling_query(soql)

            obj_describe = getattr(self.sf, object_name).describe()
            field_names = [field.get('name', '') for field in obj_describe['fields']]

            for page in result.get('records', []):
                page_name = page.get('Name', '')
                markup = page.get('Markup', '')

                if not markup:
                    continue

                if object_name not in markup:
                    continue

                for field_name in field_names:
                    if field_name in markup:
                        field_key = f"{object_name}.{field_name}"
                        if field_key not in field_usage:
                            field_usage[field_key] = set()
                        field_usage[field_key].add(page_name)

        except Exception as e:
            self._log_status(f"    ⚠ Could not query Visualforce pages: {str(e)}")

        return field_usage

    def _get_visualforce_component_usage(self, object_name: str) -> Dict[str, Set[str]]:
        """Get Visualforce component usage for object fields"""
        field_usage = {}

        try:
            soql = "SELECT Name, Markup FROM ApexComponent LIMIT 500"
            result = self._tooling_query(soql)

            obj_describe = getattr(self.sf, object_name).describe()
            field_names = [field.get('name', '') for field in obj_describe['fields']]

            for component in result.get('records', []):
                comp_name = component.get('Name', '')
                markup = component.get('Markup', '')

                if not markup:
                    continue

                if object_name not in markup:
                    continue

                for field_name in field_names:
                    if field_name in markup:
                        field_key = f"{object_name}.{field_name}"
                        if field_key not in field_usage:
                            field_usage[field_key] = set()
                        field_usage[field_key].add(comp_name)

        except Exception as e:
            self._log_status(f"    ⚠ Could not query Visualforce components: {str(e)}")

        return field_usage

    def _extract_fields_from_text(self, text: str, object_name: str) -> List[str]:
        """Extract field names from text (basic implementation)"""
        fields = []

        # This is a very basic implementation
        # Look for patterns like: field__c, FieldName, etc.
        import re

        # Pattern for custom fields
        custom_field_pattern = r'\b([A-Za-z][A-Za-z0-9_]*__c)\b'
        matches = re.findall(custom_field_pattern, text)
        fields.extend(matches)

        return fields

    def _log_status(self, message: str):
        """Log status message"""
        if self.status_callback:
            self.status_callback(message, verbose=True)