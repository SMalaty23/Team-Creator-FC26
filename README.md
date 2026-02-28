⚽ FC 26 Team Creator & Database Automation Tool
Overview

This project is a Python-based automation system designed to programmatically create and inject fully functional teams into FC 26 (FIFA database structure).

It handles:

Squad generation

Starting XI optimization

Captain selection

Team database insertion

Formation creation

Mentality configuration

Stadium linking

National team linking

Automatic file encoding detection

Dynamic header parsing for compatibility across database versions

The tool eliminates manual database editing and ensures structural consistency across all required game files.

🔧 Core Features
🧠 Intelligent Squad Builder

Builds a balanced 4-3-3 starting XI

Considers:

Primary position

Overall rating (OVR)

Position penalties for secondary roles

Automatically assigns captain (highest-rated outfield player)

🌍 National Team Mode

Filters players by:

Nationality

Gender

Blacklist rules

Automatically limits squad to 26 players

Creates balanced reserves (defenders / midfielders / forwards)

📂 Multi-File Database Injection

Automatically appends data into:

teams.txt

teamplayerlinks.txt

teamsheets.txt

formations.txt

mentalities.txt

teamnationlinks.txt

teamstadiumlinks.txt

Includes:

Header parsing for column-safe insertion

Auto-detection of UTF-8 vs UTF-16 encoding

Automatic ID incrementation

Safe removal of conflicting team links (e.g., team ID 111592)

⚙ Technical Concepts Demonstrated

Object-Oriented Design

File I/O with encoding detection

CSV / tab-delimited parsing

Dynamic header indexing

Data synchronization across multiple database files

Algorithmic team selection logic

Constraint-based squad construction

Controlled auto-increment ID generation

Error handling with traceback debugging

🧮 Squad Selection Algorithm

The starting XI builder:

Defines acceptable positions per formation slot.

Applies a configurable OVR penalty for secondary positions.

Scores players dynamically.

Selects the highest adjusted value.

Fills remaining gaps via fallback passes.

Assigns captain automatically.

This ensures realistic team strength distribution rather than naive position matching.

🎯 Problem Solved

Manual FC database editing is:

Repetitive

Error-prone

Inconsistent across files

Time-consuming

This tool creates full structural consistency in one automated pipeline.

👨‍💻 Author

Samer Malaty
Computer Science Student
Focused on automation, data modeling, and sports simulation systems.
