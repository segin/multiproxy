# Product Guidelines

## Prose and Communication Style
- **Direct & Technical:** Documentation and system messages should be precise, technical, and free of unnecessary fluff. Focus on clarity and actionable information.
- **Error Messages:** Should be descriptive and provide clear indicators of what went wrong and, where possible, how to fix it.

## User Experience and Interaction
- **Dashboard Priority:** A balanced view of real-time metrics, detailed logs, and high-level summaries.
- **Visual-First Metrics:** Use dynamic charts and graphs to represent real-time activity and token usage trends.
- **Log-Centric Activity Views:** Provide granular, filterable tables for detailed analysis of proxy traffic and error logs.
- **High-Level Summary Widgets:** Offer quick "at-a-glance" cards for system health, backend status, and total token consumption.

## Aesthetic and Branding
- **Utilitarian / Industrial:** The visual design should prioritize function over form. Use high-contrast colors, clear typography, and a "no-nonsense" layout that emphasizes utility.
- **Consistency:** Ensure the CLI output and the web dashboard share the same naming conventions and technical terminology.

## Design Principles
- **Efficiency:** The interface should be responsive and provide immediate feedback for all user actions.
- **Scalability:** The dashboard must remain usable and performant even when monitoring dozens of backend servers and high-volume traffic.
- **Transparency:** All proxy decisions (e.g., failover events, load balancing choices) should be clearly observable in the logs.
