# Contributing to 0BS1D1VM

Welcome, fren! We're building the first open-source adversarial range for AI agents, and we need your help.

## How to Contribute

### Adding Scenarios

This is the highest-impact contribution you can make. Every new scenario makes the range more valuable for everyone.

1. **Fork the repo**
2. **Create your scenario:**
   ```bash
   obsidium create my-scenario --template <category>
   ```
3. **Edit the YAML file** — define the agent, objectives, and hints
4. **Validate:**
   ```bash
   obsidium validate scenarios/<category>/my-scenario.yaml
   ```
5. **Test it** against at least 2 different models
6. **Submit a PR** with:
   - The scenario YAML
   - A brief description of what it tests
   - Which models you tested against
   - Sample attack payloads that work (for the hints)

### Scenario Quality Guidelines

- **Realistic:** Based on real-world attack surfaces, not contrived puzzles
- **Educational:** Each scenario should teach something about AI security
- **Testable:** Objectives must be scorable (automated or semi-automated)
- **Documented:** Clear description, good hints, proper metadata
- **Layered:** Tag which layers of the attack surface are targeted

### Adding Scorers

Custom scoring functions go in `obsidium/scoring/scorers.py`:

```python
def my_custom_scorer(messages: list[Message], context: dict) -> float:
    """
    Score from 0.0 (objective not achieved) to 1.0 (fully achieved).
    
    Args:
        messages: Full conversation history
        context: Scenario context (system_prompt, secrets, etc.)
    
    Returns:
        float between 0.0 and 1.0
    """
    # Your scoring logic here
    return 0.0
```

### Adding Defense Layers

Custom defense layers go in `obsidium/defenses/layers.py`:

```python
class MyDefense(DefenseLayer):
    def name(self) -> str:
        return "my_defense"
    
    def check(self, content: str, context: dict | None = None) -> DefenseResult:
        # Your defense logic
        return DefenseResult(blocked=False)
```

### Adding Model Providers

To add a new model provider, implement the `ModelProvider` interface in `obsidium/core/models.py`.

## Code Style

- Python 3.10+
- Type hints everywhere
- Docstrings for public APIs
- We use `ruff` for linting

## Philosophy

- **Offense IS defense** — every scenario is a lesson in both attack and defense
- **Open source makes everyone safer** — share what you find
- **No gatekeeping** — anyone can contribute regardless of background
- **Real-world relevance** — no CTF puzzles without practical applications

## Code of Conduct

- Be excellent to each other
- No malicious use of the range against real systems
- Responsible disclosure for real-world vulnerabilities
- Credit researchers and contributors

---

*Fortes fortuna iuvat. Fortune favors the bold.*
