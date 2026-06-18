# humanproof — Session Anchor

**Research spec:** `../tech-research/14-Gaming/generative-motor-noise-fingerprinting-detecting-ai-by-mo/README.md`  
**One-liner:** Detect AI input from human neuromuscular SDE signatures — generalizes to bot/fraud detection  
**Phase:** backlog  
**Stack:** Python, numpy, scipy, scikit-learn  

## Key decisions
- README should read like a short paper — this project earns academic credibility
- Generalizes beyond gaming: bot detection, fraud, CAPTCHA replacement
<!-- more decisions as sessions progress -->

## Next step
Read the research spec carefully (SDE model of human motor control), then implement the hidden-state SDE fitting.

## MVP definition
- `pip install humanproof` works
- Fits hidden-state SDE model of human motor control to input event stream
- Computes likelihood ratio under human-plant model vs smoothed-AI model
- API: `humanproof.score(events) → (human_probability, confidence_interval)`
- Demo dataset: recorded human mouse input vs programmatic movement
- Demo: human input scores > 0.8, programmatic input < 0.3 consistently
- README reads like a mini-paper: problem, mathematical model, results, API
