#!/usr/bin/env python3
"""
Informatica PowerCenter Expression Validator
Validates DECODE/SQL expressions for syntax, logic, and data consistency
"""

import re
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum


class SeverityLevel(Enum):
    """Issue severity levels"""
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class ValidationIssue:
    """Represents a validation issue"""
    severity: SeverityLevel
    code: str
    message: str
    line_num: Optional[int] = None
    suggestion: Optional[str] = None


class ExpressionValidator:
    """Validates Informatica expression transformations"""

    def __init__(self):
        self.issues: List[ValidationIssue] = []
        self.expression: str = ""
        self.lines: List[str] = []

    def validate(self, expression: str, field_name: str = "PERIOD_BEGIN_DT") -> Dict:
        """
        Main validation method
        
        Args:
            expression: The expression string to validate
            field_name: Name of the target field (for context)
            
        Returns:
            Dictionary containing validation results
        """
        self.expression = expression
        self.issues = []
        self.lines = expression.split('\n')

        # Run all validation checks
        self._check_syntax()
        self._check_bracket_balance()
        self._check_decode_structure()
        self._check_undefined_variables()
        self._check_logic_completeness()
        self._check_data_type_consistency()
        self._check_performance_issues()

        return self._generate_report(field_name)

    def _check_syntax(self):
        """Check for basic syntax errors"""
        # Check for unmatched quotes
        single_quotes = self.expression.count("'")
        if single_quotes % 2 != 0:
            self.issues.append(ValidationIssue(
                severity=SeverityLevel.ERROR,
                code="SYNTAX_001",
                message="Unmatched single quotes detected",
                suggestion="Verify all string literals are properly quoted"
            ))

        # Check for invalid SQL operators
        invalid_patterns = [
            (r'\s+or\s+', 'Use uppercase OR'),
            (r'\s+and\s+', 'Use uppercase AND'),
        ]
        
        for pattern, suggestion in invalid_patterns:
            if re.search(pattern, self.expression, re.IGNORECASE):
                # Convert to lowercase check to find mixed case
                if re.search(pattern, self.expression):
                    self.issues.append(ValidationIssue(
                        severity=SeverityLevel.WARNING,
                        code="SYNTAX_002",
                        message=f"Mixed case logical operators found",
                        suggestion=suggestion
                    ))

    def _check_bracket_balance(self):
        """Verify balanced parentheses in expression"""
        open_count = self.expression.count('(')
        close_count = self.expression.count(')')
        
        if open_count != close_count:
            self.issues.append(ValidationIssue(
                severity=SeverityLevel.ERROR,
                code="SYNTAX_003",
                message=f"Unbalanced parentheses: {open_count} open, {close_count} close",
                suggestion="Add missing closing parentheses"
            ))

        # Check nesting depth
        max_depth = 0
        current_depth = 0
        for char in self.expression:
            if char == '(':
                current_depth += 1
                max_depth = max(max_depth, current_depth)
            elif char == ')':
                current_depth -= 1
        
        if max_depth > 8:
            self.issues.append(ValidationIssue(
                severity=SeverityLevel.WARNING,
                code="SYNTAX_004",
                message=f"High nesting depth detected: {max_depth} levels",
                suggestion="Consider breaking into multiple expressions or mappings for maintainability"
            ))

    def _check_decode_structure(self):
        """Validate DECODE function structure"""
        # Count DECODE functions
        decode_count = self.expression.count('DECODE(')
        
        # Verify nested DECODE structure
        if decode_count > 1:
            self.issues.append(ValidationIssue(
                severity=SeverityLevel.INFO,
                code="DECODE_001",
                message=f"Nested DECODE functions detected: {decode_count} levels",
                suggestion="Nested DECODEs are valid but add complexity. Consider refactoring if maintainability is an issue"
            ))

        # Check for DECODE(TRUE, ...) pattern
        if 'DECODE(TRUE,' in self.expression:
            self.issues.append(ValidationIssue(
                severity=SeverityLevel.INFO,
                code="DECODE_002",
                message="DECODE(TRUE, ...) pattern used (IF-THEN-ELSE simulation)",
                suggestion="This pattern is valid and commonly used in Informatica"
            ))

    def _check_undefined_variables(self):
        """Check for undefined variable references"""
        # Extract all variable references (ALL_CAPS or mixed_CASE)
        var_pattern = r'\b([A-Z_][A-Z0-9_]*)\b'
        variables = set(re.findall(var_pattern, self.expression))

        # Known Informatica functions and keywords
        known_functions = {
            'DECODE', 'SUBSTR', 'TRUE', 'FALSE', 'NULL', 'OR', 'AND',
            'TO_DATE', 'TO_CHAR', 'TO_INTEGER', 'LTRIM', 'RTRIM',
            'LENGTH', 'UPPER', 'LOWER', 'ISNULL', 'ABS', 'ROUND'
        }

        # Expected variables from mapping context
        expected_variables = {
            'PAYFLAG', 'CODE', 'SADATE', 'CYCLE', 'PREV_PRIOR_YR', 'PRIORYR'
        }

        # Check for undefined variables
        for var in sorted(variables):
            if var not in known_functions and var not in expected_variables:
                # Might be a literal or column name
                if not var.replace('_', '').isalnum():
                    continue
                
                self.issues.append(ValidationIssue(
                    severity=SeverityLevel.WARNING,
                    code="VAR_001",
                    message=f"Unknown variable '{var}' - verify it's defined in mapping",
                    suggestion=f"Add '{var}' to incoming ports or local variables"
                ))

        # Verify all expected variables are present
        for expected in expected_variables:
            if expected not in variables:
                self.issues.append(ValidationIssue(
                    severity=SeverityLevel.WARNING,
                    code="VAR_002",
                    message=f"Expected variable '{expected}' not found in expression",
                    suggestion=f"This may be intentional if using conditional logic"
                ))

    def _check_logic_completeness(self):
        """Check for logical completeness and edge cases"""
        # Count conditions in outer DECODE(TRUE, ...)
        condition_pairs = re.findall(
            r"PAYFLAG='[^']+'\s+AND\s+\([^)]+\)",
            self.expression
        )

        issues_found = []

        # Check Condition 1: SAC/SAF/SAT
        if "PAYFLAG='CYCLE' AND (CODE='SAC' OR CODE='SAF' OR CODE='SAT')" in self.expression:
            issues_found.append("Condition 1: SAC/SAF/SAT returns SADATE ✓")
        else:
            self.issues.append(ValidationIssue(
                severity=SeverityLevel.ERROR,
                code="LOGIC_001",
                message="First condition for SAC/SAF/SAT may be malformed",
                suggestion="Verify: PAYFLAG='CYCLE' AND (CODE='SAC' OR CODE='SAF' OR CODE='SAT')"
            ))

        # Check Condition 2: CHG/NSF/RST/FPF/FSF
        if "PAYFLAG='CYCLE' AND (CODE='CHG' or CODE='NSF' OR CODE='RST' OR CODE='FPF' OR CODE='FSF')" in self.expression:
            issues_found.append("Condition 2: CHG/NSF/RST/FPF/FSF with nested DECODE ✓")
        else:
            self.issues.append(ValidationIssue(
                severity=SeverityLevel.WARNING,
                code="LOGIC_002",
                message="Second condition for CHG/NSF/RST/FPF/FSF may be malformed",
                suggestion="Verify all CODE values are correctly spelled and quoted"
            ))

        # Check for unhandled CODE values
        handled_codes = {
            'SAC', 'SAF', 'SAT',
            'CHG', 'NSF', 'RST', 'FPF', 'FSF'
        }
        self.issues.append(ValidationIssue(
            severity=SeverityLevel.WARNING,
            code="LOGIC_003",
            message=f"Only {len(handled_codes)} CODE values explicitly handled",
            suggestion="Verify final NULL clause is intentional. Consider handling additional CODE values if applicable"
        ))

        # Check CYCLE values coverage
        cycle_patterns = [
            '1Q', '2Q', '3Q', '4Q',
            '1S', '2S', '3S', '4S',
            '1QV', '2QV', '3QV', '4QV',
            '1SV', '2SV', '3SV', '4SV',
            '1R', '2R', '3R', '4R'
        ]
        
        missing_cycles = []
        for cycle in cycle_patterns:
            if cycle not in self.expression:
                missing_cycles.append(cycle)

        if missing_cycles:
            self.issues.append(ValidationIssue(
                severity=SeverityLevel.WARNING,
                code="LOGIC_004",
                message=f"Missing CYCLE values: {', '.join(missing_cycles[:3])}{'...' if len(missing_cycles) > 3 else ''}",
                suggestion="Verify if all CYCLE patterns should be supported"
            ))

    def _check_data_type_consistency(self):
        """Verify data type consistency in expressions"""
        # Check date format consistency
        date_pattern = r"'(\d{2}/\d{2}/')"
        dates = re.findall(date_pattern, self.expression)
        
        if dates:
            self.issues.append(ValidationIssue(
                severity=SeverityLevel.INFO,
                code="TYPE_001",
                message=f"Date string concatenation detected: {len(dates)} instances",
                suggestion="Ensure PRIORYR and PREV_PRIOR_YR are numeric (4-digit year) for proper concatenation"
            ))

        # Check SUBSTR usage on CYCLE
        substr_count = self.expression.count('SUBSTR(CYCLE')
        if substr_count > 0:
            self.issues.append(ValidationIssue(
                severity=SeverityLevel.INFO,
                code="TYPE_002",
                message=f"SUBSTR used {substr_count} times on CYCLE field",
                suggestion="Ensure CYCLE field is VARCHAR/CHAR type with sufficient length"
            ))

        # Verify year field types
        if 'PREV_PRIOR_YR' in self.expression or 'PRIORYR' in self.expression:
            self.issues.append(ValidationIssue(
                severity=SeverityLevel.INFO,
                code="TYPE_003",
                message="Year fields (PREV_PRIOR_YR, PRIORYR) used in string concatenation",
                suggestion="Ensure these fields are numeric type; will be implicitly converted to string"
            ))

    def _check_performance_issues(self):
        """Identify potential performance concerns"""
        # Check for SUBSTR on same field multiple times
        cycle_substr = self.expression.count('SUBSTR(CYCLE')
        if cycle_substr > 10:
            self.issues.append(ValidationIssue(
                severity=SeverityLevel.WARNING,
                code="PERF_001",
                message=f"SUBSTR(CYCLE) called {cycle_substr} times",
                suggestion="Consider creating a local variable for SUBSTR(CYCLE,1,2) to improve performance"
            ))

        # Check for redundant nested DECODEs
        nested_decode = self.expression.count('DECODE(TRUE')
        if nested_decode > 2:
            self.issues.append(ValidationIssue(
                severity=SeverityLevel.WARNING,
                code="PERF_002",
                message=f"Multiple nested DECODE(TRUE) statements ({nested_decode})",
                suggestion="Consider breaking into separate expressions or using a lookup table for CYCLE logic"
            ))

    def _generate_report(self, field_name: str) -> Dict:
        """Generate validation report"""
        critical_count = sum(1 for i in self.issues if i.severity == SeverityLevel.CRITICAL)
        error_count = sum(1 for i in self.issues if i.severity == SeverityLevel.ERROR)
        warning_count = sum(1 for i in self.issues if i.severity == SeverityLevel.WARNING)
        info_count = sum(1 for i in self.issues if i.severity == SeverityLevel.INFO)

        is_valid = critical_count == 0 and error_count == 0

        return {
            'field_name': field_name,
            'is_valid': is_valid,
            'summary': {
                'total_issues': len(self.issues),
                'critical': critical_count,
                'errors': error_count,
                'warnings': warning_count,
                'info': info_count
            },
            'issues': [
                {
                    'severity': issue.severity.value,
                    'code': issue.code,
                    'message': issue.message,
                    'suggestion': issue.suggestion,
                    'line': issue.line_num
                }
                for issue in self.issues
            ],
            'expression_stats': {
                'length': len(self.expression),
                'lines': len(self.lines),
                'nesting_depth': self._calculate_nesting_depth(),
                'functions_count': self.expression.count('(') - self.expression.count('||'),
                'variables_used': len(re.findall(r'\b[A-Z_][A-Z0-9_]*\b', self.expression))
            }
        }

    def _calculate_nesting_depth(self) -> int:
        """Calculate maximum nesting depth"""
        max_depth = 0
        current_depth = 0
        for char in self.expression:
            if char == '(':
                current_depth += 1
                max_depth = max(max_depth, current_depth)
            elif char == ')':
                current_depth -= 1
        return max_depth


def print_report(report: Dict):
    """Pretty print validation report"""
    print("\n" + "="*80)
    print(f"INFORMATICA EXPRESSION VALIDATION REPORT")
    print(f"Field: {report['field_name']}")
    print("="*80)

    # Status
    status = "✓ VALID" if report['is_valid'] else "✗ INVALID"
    print(f"\nStatus: {status}")

    # Summary
    summary = report['summary']
    print(f"\nIssue Summary:")
    print(f"  Total Issues: {summary['total_issues']}")
    print(f"  Critical: {summary['critical']}")
    print(f"  Errors: {summary['errors']}")
    print(f"  Warnings: {summary['warnings']}")
    print(f"  Info: {summary['info']}")

    # Expression Stats
    stats = report['expression_stats']
    print(f"\nExpression Statistics:")
    print(f"  Length: {stats['length']} characters")
    print(f"  Lines: {stats['lines']}")
    print(f"  Max Nesting Depth: {stats['nesting_depth']}")
    print(f"  Functions: {stats['functions_count']}")
    print(f"  Variables: {stats['variables_used']}")

    # Issues
    if report['issues']:
        print(f"\nDetailed Issues:")
        print("-"*80)
        for issue in report['issues']:
            print(f"\n[{issue['severity']}] {issue['code']}")
            print(f"Message: {issue['message']}")
            if issue['suggestion']:
                print(f"Suggestion: {issue['suggestion']}")

    print("\n" + "="*80 + "\n")


if __name__ == "__main__":
    # Test with the provided expression
    expression = """DECODE(TRUE,
  PAYFLAG='CYCLE' AND (CODE='SAC' OR CODE='SAF' OR CODE='SAT' ) ,SADATE,
  PAYFLAG='CYCLE' AND (CODE='CHG' or CODE='NSF' OR CODE='RST' OR CODE='FPF' OR CODE='FSF'),DECODE(TRUE,
SUBSTR(CYCLE,1,2)= '1Q',('07/01/'||PREV_PRIOR_YR),
SUBSTR(CYCLE,1,2)='2Q',('10/01/'||PREV_PRIOR_YR),
SUBSTR(CYCLE,1,2)='3Q',('01/01/'||PRIORYR),
SUBSTR(CYCLE,1,2)='4Q',('04/01/'||PRIORYR),
SUBSTR(CYCLE,1,2)='1S',('07/01/'||PREV_PRIOR_YR),
SUBSTR(CYCLE,1,2)='2S',('10/01/'||PREV_PRIOR_YR),
SUBSTR(CYCLE,1,2)='4S',('04/01/'||PRIORYR),
SUBSTR(CYCLE,1,2)='3S',('01/01/'||PRIORYR),
SUBSTR(CYCLE,1,3)='1QV',('07/01/'||PREV_PRIOR_YR),
SUBSTR(CYCLE,1,3)='2QV',('10/01/'||PREV_PRIOR_YR),
SUBSTR(CYCLE,1,3)='3QV',('01/01/'||PRIORYR),
SUBSTR(CYCLE,1,3)='4QV',('04/01/'||PRIORYR),
SUBSTR(CYCLE,1,3)='1SV',('07/01/'||PREV_PRIOR_YR),
SUBSTR(CYCLE,1,3)='2SV',('10/01/'||PREV_PRIOR_YR),
SUBSTR(CYCLE,1,3)='4SV',('04/01/'||PRIORYR),
SUBSTR(CYCLE,1,3)='3SV',('01/01/'||PRIORYR),
SUBSTR(CYCLE,1,2)='1R',('07/01/'||PREV_PRIOR_YR),
SUBSTR(CYCLE,1,2)='2R',('10/01/'||PREV_PRIOR_YR),
SUBSTR(CYCLE,1,2)='3R',('01/01/'||PRIORYR),
SUBSTR(CYCLE,1,2)='4R',('04/01/'||PRIORYR),
NULL),NULL
    )"""

    validator = ExpressionValidator()
    report = validator.validate(expression, "PERIOD_BEGIN_DT")
    print_report(report)
