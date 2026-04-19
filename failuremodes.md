# ShopWave AI - System Failure Modes & Handling

When building an AI agent that runs completely on its own, the AI can sometimes get confused, hallucinate, or make mistakes. Below are three major failure scenarios we encountered while building ShopWave AI, and the detailed steps we took to fix them.

### Scenario 1: AI Formatting Mistakes & Crashes

**The Problem:** For our system to work automatically, we need the AI to output its final decision in a very strict, readable data format (like JSON). However, the AI would sometimes act too "chatty." It would add extra conversational words (like "Here is the output you requested:") or wrap the data in weird brackets. When our main system tried to read this messy output, it would crash and fail to send a reply to the customer.

**How We Handled It:** Instead of trusting the AI to format things perfectly, we built a smart "Cleaning Tool" (an Extractor) at the very end of the process. If the AI messes up the format, this tool acts like a detective. It scans through all the messy text, ignores the conversational filler, removes any weird brackets, and safely pulls out *only* the exact email message we need. Because of this safety net, our system never crashes due to AI typos, guaranteeing 100% uptime.

### Scenario 2: Getting Stuck on Missing Information

**The Problem:** Customers often send emails that lack important details, like saying "Where is my refund?" without actually providing their Order ID. In the early stages, if the AI didn't have an Order ID, it would panic. It would either try to guess a fake Order ID to keep going, or it would get stuck in an endless "thinking" loop trying to solve an impossible problem. This wastes time and computer resources.

**How We Handled It:** We gave the AI a strict "Stop and Ask" rule. Now, when a vague email comes in, the AI is programmed to first search our database using the customer's email address. If it still cannot find a matching order, the AI is strictly blocked from guessing. Instead, it is forced to immediately stop its thought process and send a polite reply to the customer saying, "Could you please provide your Order ID?" This prevents the AI from hallucinating fake actions.

### Scenario 3: Conflicting Business Rules

**The Problem:** A business has many overlapping rules. For example, we have a rule that says "Refund items under $200 automatically" and another rule that says "Do not refund if 30 days have passed." We found that if a customer wanted a refund for a $250 item, and they were also 5 days late, the AI would sometimes get confused about which rule was more important. This confusion could lead to the AI accidentally giving away free money.

**How We Handled It:** We fixed this by building a strict step-by-step checklist that the AI cannot skip. It must check the rules in an exact order: first the time limit, then the warranty, and finally the price. More importantly, we added a safety block. If a ticket triggers any warning flag—like the item being too expensive, or the customer having a history of returning too many things—the AI is completely blocked from clicking the "Issue Refund" button. It is forced to hand the ticket over to a real human manager for review. This keeps the business perfectly safe from bad AI decisions.