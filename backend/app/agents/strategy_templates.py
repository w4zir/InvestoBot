"""
Strategy templates for common trading patterns.

Templates provide structured patterns that the LLM can instantiate with parameters,
while still allowing for custom strategy generation.
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class StrategyTemplate(BaseModel):
    """A strategy template with metadata and parameter definitions."""
    
    template_id: str
    name: str
    description: str
    type: str  # "volatility_breakout", "pairs_trading", "intraday_mean_reversion"
    required_params: Dict[str, Any] = Field(default_factory=dict)
    optional_params: Dict[str, Any] = Field(default_factory=dict)
    example_rules: List[Dict[str, Any]] = Field(default_factory=list)
    example_params: Dict[str, Any] = Field(default_factory=dict)


class TemplateRegistry:
    """Registry for managing strategy templates."""
    
    def __init__(self):
        self._templates: Dict[str, StrategyTemplate] = {}
        self._register_default_templates()
    
    def _register_default_templates(self):
        """Register the default strategy templates."""
        
        # Volatility Breakout Template
        volatility_breakout = StrategyTemplate(
            template_id="volatility_breakout",
            name="Volatility Breakout",
            description=(
                "Entry on volatility expansion above threshold, exit on reversion. "
                "Uses ATR or Bollinger Bands to detect volatility breakouts. "
                "Suitable for trending markets with high volatility periods."
            ),
            type="volatility_breakout",
            required_params={
                "volatility_indicator": "atr",  # or "bollinger"
                "lookback_period": 20,
                "volatility_threshold": 1.5,  # multiplier of average volatility
            },
            optional_params={
                "entry_threshold": 1.5,
                "exit_threshold": 0.8,
                "stop_loss_pct": 0.02,
                "take_profit_pct": 0.05,
            },
            example_rules=[
                {
                    "type": "entry",
                    "indicator": "volatility_breakout",
                    "params": {
                        "indicator": "atr",
                        "lookback": 20,
                        "threshold": 1.5,
                        "direction": "long"
                    }
                },
                {
                    "type": "exit",
                    "indicator": "volatility_reversion",
                    "params": {
                        "indicator": "atr",
                        "lookback": 20,
                        "threshold": 0.8
                    }
                }
            ],
            example_params={
                "position_sizing": "fixed_fraction",
                "fraction": 0.02,
                "timeframe": "1d"
            }
        )
        
        # Pairs Trading Template
        pairs_trading = StrategyTemplate(
            template_id="pairs_trading",
            name="Pairs Trading",
            description=(
                "Cointegration-based pairs trading with spread mean-reversion. "
                "Identifies correlated pairs and trades the spread when it deviates from mean. "
                "Requires two symbols in universe that are historically correlated."
            ),
            type="pairs_trading",
            required_params={
                "pair_symbols": ["SYMBOL1", "SYMBOL2"],
                "spread_lookback": 60,
                "entry_zscore": 2.0,
                "exit_zscore": 0.5,
            },
            optional_params={
                "cointegration_lookback": 252,
                "hedge_ratio": None,  # auto-calculate
                "stop_loss_zscore": 3.0,
            },
            example_rules=[
                {
                    "type": "entry",
                    "indicator": "pairs_spread_zscore",
                    "params": {
                        "symbol1": "AAPL",
                        "symbol2": "MSFT",
                        "lookback": 60,
                        "entry_threshold": 2.0,
                        "direction": "long"  # long spread = long symbol1, short symbol2
                    }
                },
                {
                    "type": "exit",
                    "indicator": "pairs_spread_zscore",
                    "params": {
                        "symbol1": "AAPL",
                        "symbol2": "MSFT",
                        "lookback": 60,
                        "exit_threshold": 0.5
                    }
                }
            ],
            example_params={
                "position_sizing": "fixed_fraction",
                "fraction": 0.03,
                "timeframe": "1d"
            }
        )
        
        # Intraday Mean-Reversion Template
        intraday_mean_reversion = StrategyTemplate(
            template_id="intraday_mean_reversion",
            name="Intraday Mean-Reversion",
            description=(
                "Short-term mean reversion strategy using z-score thresholds. "
                "Trades on intraday price deviations from moving average. "
                "Best for range-bound markets with mean-reverting behavior."
            ),
            type="intraday_mean_reversion",
            required_params={
                "mean_lookback": 20,
                "entry_zscore": 2.0,
                "exit_zscore": 0.5,
            },
            optional_params={
                "timeframe": "1h",  # intraday timeframe
                "stop_loss_pct": 0.01,
                "max_holding_period": 4,  # hours
            },
            example_rules=[
                {
                    "type": "entry",
                    "indicator": "zscore",
                    "params": {
                        "window": 20,
                        "entry_threshold": -2.0,  # oversold
                        "direction": "long"
                    }
                },
                {
                    "type": "exit",
                    "indicator": "zscore",
                    "params": {
                        "window": 20,
                        "exit_threshold": 0.5  # return to mean
                    }
                }
            ],
            example_params={
                "position_sizing": "fixed_fraction",
                "fraction": 0.02,
                "timeframe": "1h"
            }
        )
        
        self.register(volatility_breakout)
        self.register(pairs_trading)
        self.register(intraday_mean_reversion)
    
    def register(self, template: StrategyTemplate):
        """Register a template."""
        self._templates[template.template_id] = template
    
    def get(self, template_id: str) -> Optional[StrategyTemplate]:
        """Get a template by ID."""
        return self._templates.get(template_id)
    
    def list_all(self) -> List[StrategyTemplate]:
        """List all registered templates."""
        return list(self._templates.values())
    
    def get_by_type(self, template_type: str) -> List[StrategyTemplate]:
        """Get all templates of a specific type."""
        return [t for t in self._templates.values() if t.type == template_type]
    
    def get_template_examples(self) -> List[Dict[str, Any]]:
        """Get example instantiations of all templates for few-shot learning."""
        examples = []
        for template in self._templates.values():
            examples.append({
                "template_id": template.template_id,
                "template_name": template.name,
                "description": template.description,
                "example_strategy": {
                    "strategy_id": f"example_{template.template_id}",
                    "name": f"Example {template.name}",
                    "description": template.description,
                    "universe": ["AAPL", "MSFT"] if template.type != "pairs_trading" else ["AAPL", "MSFT"],
                    "rules": template.example_rules,
                    "params": template.example_params
                }
            })
        return examples


# Global registry instance
_template_registry = TemplateRegistry()


def get_template_registry() -> TemplateRegistry:
    """Get the global template registry."""
    return _template_registry

