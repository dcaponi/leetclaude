# Quiz bank for trivial tasks (renames, typos, one-line config). Multiple choice: choices + answer (index).
# Written answer: accept (list of case-insensitive regexes) + answer (display text).
# tags pick questions relevant to the repo: python javascript typescript go rust ruby java cpp csharp sql
# general git http testing design.

QUIZ = [
    dict(id="hash-lookup", tags=["general"],
         q="What is the average-case time complexity of looking up a key in a hash map?",
         choices=["O(1)", "O(log n)", "O(n)", "Depends on how much coffee the hash function had"],
         answer=0, why="Hashing goes straight to a bucket; collisions make the worst case O(n), but the average is O(1)."),
    dict(id="git-undo-commit", tags=["git"],
         q="Which command undoes the last commit but keeps its changes staged?",
         accept=[r"git\s+reset\s+--soft\s+head(~1|\^)?"], answer="git reset --soft HEAD~1",
         why="--soft moves HEAD back and leaves the index and working tree alone."),

    # ---------------------------------------------------------------- general
    dict(id="float-equality", tags=["general"],
         q="In most languages, what does 0.1 + 0.2 == 0.3 evaluate to?",
         choices=["true", "false", "A compile error", "true, but only on Fridays"],
         answer=1, why="0.1 and 0.2 have no exact binary representation, so the sum is 0.30000000000000004. "
                       "Compare floats with a tolerance, or use a decimal type for money."),
    dict(id="dynamic-array-append", tags=["general"],
         q="What is the amortized time complexity of appending to a dynamic array (Python list, Go slice, Rust Vec)?",
         choices=["O(1)", "O(log n)", "O(n)", "O(n), but it builds character"],
         answer=0, why="When the array is full it grows by a constant factor, so the rare O(n) copy averages out "
                       "to O(1) per append."),
    dict(id="binary-search-precondition", tags=["general"],
         q="Binary search only works if the input has one property. What is it?",
         accept=[r"sort", r"\bordered\b", r"monoton"], answer="The input must be sorted",
         why="Each step discards half the range based on a comparison, which is only valid when the data is sorted "
             "(or the predicate is monotonic)."),

    # -------------------------------------------------------------------- git
    dict(id="git-revert-shared", tags=["git"],
         q="A bad commit is already on the shared main branch. What is the safe way to undo it?",
         choices=["git reset --hard HEAD~1, then git push --force", "git revert <sha>", "git commit --amend",
                  "Force-push and update your LinkedIn"],
         answer=1, why="revert adds a new commit that inverts the bad one, so it does not rewrite history that "
                       "teammates have already pulled."),
    dict(id="git-bisect", tags=["git", "testing"],
         q="Which git command binary-searches the commit history to find the commit that introduced a bug?",
         accept=[r"bisect"], answer="git bisect",
         why="You mark one good and one bad commit, and git checks out the midpoint each step. "
             "git bisect run <script> automates it."),

    # ------------------------------------------------------------------- http
    dict(id="http-post-not-idempotent", tags=["http"],
         q="Which HTTP method is NOT idempotent by definition?",
         choices=["PUT", "DELETE", "POST", "GET"],
         answer=2, why="Two identical POSTs can create two resources. Repeated PUT or DELETE calls leave the server "
                       "in the same state as one call."),
    dict(id="http-401-vs-403", tags=["http"],
         q="The user is logged in, but their role does not allow this action. Which status code fits?",
         choices=["401 Unauthorized", "403 Forbidden", "400 Bad Request", "418 I'm a teapot"],
         answer=1, why="401 means the server does not know who you are (missing or bad credentials). "
                       "403 means it knows who you are, and the answer is still no."),
    dict(id="http-429", tags=["http"],
         q="Which HTTP status code tells a client it is being rate limited?",
         accept=[r"\b429\b", r"too\s+many\s+requests"], answer="429 Too Many Requests",
         why="A 429 response often includes a Retry-After header that tells the client how long to wait."),
    dict(id="http-cors-enforcer", tags=["http", "javascript"],
         q="Who enforces CORS (Cross-Origin Resource Sharing)?",
         choices=["The browser", "The server's firewall", "The DNS resolver",
                  "The intern who last touched the nginx config"],
         answer=0, why="The server only sends Access-Control-* headers. The browser decides whether page JavaScript "
                       "may read the response, which is why curl ignores CORS completely."),

    # ---------------------------------------------------------------- testing
    dict(id="testing-flaky", tags=["testing"],
         q="What do you call a test that passes and fails on the same code with no changes?",
         accept=[r"flak", r"non[\s-]*determinis", r"intermittent", r"heisen"], answer="A flaky test",
         why="Usual causes: timing and sleeps, shared state between tests, test order, and real network or clock "
             "calls."),
    dict(id="testing-pyramid", tags=["testing"],
         q="In the test pyramid, which kind of test should you have the most of?",
         choices=["Unit tests", "End-to-end UI tests", "Manual QA passes", "Production, also known as customers"],
         answer=0, why="Unit tests are fast, cheap and point straight at the failure. Slow, brittle end-to-end tests "
                       "belong at the narrow top."),
    dict(id="testing-coverage", tags=["testing"],
         q="Your test suite reports 100% line coverage. What does that prove?",
         choices=["The code has no bugs", "Every line ran at least once during the tests",
                  "Every combination of branches was tested", "You may now skip code review"],
         answer=1, why="Coverage measures what executed, not what was checked. A test with no assertions still "
                       "adds coverage."),

    # ----------------------------------------------------------------- design
    dict(id="design-idempotency-key", tags=["design", "http"],
         q="A payment request times out and the client retries it. What prevents a double charge?",
         choices=["A unique idempotency key that the server deduplicates on", "A longer client timeout",
                  "Retrying faster", "A strongly worded comment above the retry loop"],
         answer=0, why="A timeout does not tell the client whether the first request succeeded. The server stores "
                       "the result per key and returns it for the retry instead of charging again."),
    dict(id="design-retry-backoff", tags=["design"],
         q="A downstream service is overloaded. How should thousands of clients retry their failed calls?",
         choices=["Immediately, in a tight loop", "Exponential backoff with random jitter",
                  "Exactly once per second, all of them", "Open a ticket and retry next quarter"],
         answer=1, why="Backoff reduces load while the failure continues, and jitter stops clients from retrying "
                       "in synchronized waves (a thundering herd)."),
    dict(id="design-n-plus-one", tags=["design", "sql"],
         q="An ORM loads 100 posts in one query, then runs one more query per post to load its author. "
           "What is this anti-pattern called?",
         accept=[r"n\s*\+\s*1", r"n\s*plus\s*(1|one)\b", r"1\s*\+\s*n"], answer="The N+1 query problem",
         why="Load the authors in one batched query or a JOIN (eager loading) instead of one query per row."),

    # -------------------------------------------------------------------- sql
    dict(id="sql-null-equals", tags=["sql"],
         q="In standard SQL, what does SELECT * FROM users WHERE deleted_at = NULL return?",
         choices=["All rows where deleted_at is NULL", "No rows", "A syntax error", "Every row, as a treat"],
         answer=1, why="Any comparison with NULL is UNKNOWN, never TRUE, so no row matches. Use IS NULL."),
    dict(id="sql-composite-index", tags=["sql"],
         q="A table has one index on (last_name, first_name). Which filter can use that index efficiently?",
         choices=["WHERE first_name = 'Ada'", "WHERE last_name = 'Lovelace'",
                  "WHERE UPPER(last_name) = 'LOVELACE'", "WHERE the_index = 'please'"],
         answer=1, why="A composite B-tree index is sorted by its leftmost column first, so the filter must start "
                       "there. Wrapping the column in a function also blocks a normal index lookup."),
    dict(id="sql-read-committed", tags=["sql"],
         q="What is the lowest standard SQL isolation level that prevents dirty reads?",
         accept=[r"read[\s_-]*committed"], answer="READ COMMITTED",
         why="READ UNCOMMITTED allows dirty reads. READ COMMITTED only shows committed data, and it is "
             "PostgreSQL's default."),

    # ----------------------------------------------------------------- python
    dict(id="python-mutable-default", tags=["python"],
         q="def add(item, bucket=[]): bucket.append(item); return bucket. You call add(1), then add(2). "
           "What does the second call return?",
         choices=["[2]", "[1, 2]", "TypeError", "[2], unless Mercury is in retrograde"],
         answer=1, why="Python evaluates default values once, when the def runs, so every call shares one list. "
                       "Use bucket=None and create the list inside the function."),
    dict(id="python-late-binding", tags=["python"],
         q="What does [f() for f in [lambda: i for i in range(3)]] return?",
         choices=["[0, 1, 2]", "[2, 2, 2]", "[0, 0, 0]", "A sincere apology from the interpreter"],
         answer=1, why="A closure looks up i when it runs, not when it was created, and by then the loop has "
                       "finished at 2. Bind it early with lambda i=i: i."),

    # ------------------------------------------------- javascript / typescript
    dict(id="js-strict-equality", tags=["javascript", "typescript"],
         q="In JavaScript, what do 0 == '' and 0 === '' evaluate to?",
         choices=["true and true", "true and false", "false and false", "undefined and NaN"],
         answer=1, why="== coerces both sides first ('' becomes 0). === compares type and value with no coercion, "
                       "so prefer it."),
    dict(id="js-default-sort", tags=["javascript", "typescript"],
         q="What does [10, 9, 1].sort() return in JavaScript?",
         choices=["[1, 9, 10]", "[1, 10, 9]", "[10, 9, 1]", "A Promise that resolves to a sorted array, eventually"],
         answer=1, why="With no comparator, sort converts the elements to strings and compares them as text. "
                       "Pass (a, b) => a - b for numbers."),
    dict(id="ts-types-erased", tags=["typescript"],
         q="What does a TypeScript type annotation or 'as' assertion do at runtime?",
         choices=["Nothing; the compiler erases types", "It throws if the value has the wrong type",
                  "It converts the value to that type", "It files a bug report against the backend team"],
         answer=0, why="TypeScript checks types only at compile time. Validate untrusted data, such as API "
                       "responses, at runtime (for example with a schema validator)."),
    dict(id="ts-unknown", tags=["typescript"],
         q="Which TypeScript type accepts any value but makes you narrow it before you can use it?",
         accept=[r"\bunknown\b"], answer="unknown",
         why="any turns type checking off. unknown keeps it on and makes you check with typeof, instanceof or a "
             "type guard first."),

    # --------------------------------------------------------------------- go
    dict(id="go-nil-map", tags=["go"],
         q="In Go, what happens when you assign m[\"a\"] = 1 after var m map[string]int?",
         choices=["It works; Go creates the map lazily", "It panics: assignment to entry in nil map",
                  "It is a compile error", "The gopher writes it down for you"],
         answer=1, why="A nil map can be read (it returns zero values) but not written. Create it first with "
                       "make(map[string]int) or a map literal."),
    dict(id="go-nil-interface", tags=["go"],
         q="*MyErr implements error. func f() error { var p *MyErr; return p }. Is f() != nil true?",
         choices=["No, f returns nil", "Yes, the interface holds a typed nil pointer", "It does not compile",
                  "Only if go vet is in a bad mood"],
         answer=1, why="An interface value is nil only if both its type and its value are nil. Here the type is "
                       "*MyErr, so the error is not nil. Return a literal nil instead."),

    # ------------------------------------------------------------------- rust
    dict(id="rust-borrow-rules", tags=["rust"],
         q="In Rust, can a &mut reference and a & reference to the same value both be in use at the same time?",
         choices=["Yes, always", "No: many shared references or one mutable reference, never both",
                  "Yes, if you ask the borrow checker nicely", "Only in release builds"],
         answer=1, why="The borrow checker enforces aliasing XOR mutation at compile time. That rules out data races "
                       "and iterator invalidation."),
    dict(id="rust-question-mark", tags=["rust"],
         q="In a Rust function that returns Result, which operator returns the error early if a call fails?",
         accept=[r"^[`'\"\s]*\?[`'\";\s]*$", r"\?\s*operator", r"question[\s-]*mark", r"try\s*operator", r"\)\?"],
         answer="The ? operator",
         why="let x = parse(s)?; unwraps an Ok, or converts the Err with From and returns it from the function."),

    # ------------------------------------------------------------------- ruby
    dict(id="ruby-falsy", tags=["ruby"],
         q="In Ruby, which values are falsy?",
         choices=["false, nil, 0 and \"\"", "Only false and nil", "Only false",
                  "Anything written before the first coffee"],
         answer=1, why="In Ruby, 0, \"\" and [] are all truthy. Only false and nil are falsy."),
    dict(id="ruby-safe-navigation", tags=["ruby"],
         q="Which Ruby operator calls a method only when the receiver is not nil, and returns nil otherwise?",
         accept=[r"&\.", r"safe[\s-]*navigation", r"lonely"], answer="&. (the safe navigation operator)",
         why="user&.name returns nil when user is nil, instead of raising NoMethodError."),

    # ----------------------------------------------------------------- csharp
    dict(id="csharp-async-void", tags=["csharp"],
         q="Why should a C# method avoid async void, except for event handlers?",
         choices=["It runs synchronously", "Callers cannot await it or catch its exceptions",
                  "It is slower than async Task", "void is bad luck in async code"],
         answer=1, why="An exception in an async void method goes to the SynchronizationContext and can crash the "
                       "process. Return Task instead."),
    dict(id="csharp-string-builder", tags=["csharp"],
         q="You build one large string from 10,000 pieces in a C# loop. What should you use?",
         choices=["s += piece inside the loop", "StringBuilder", "A new thread for each piece",
                  "Recursion, for the elegance"],
         answer=1, why="C# strings are immutable, so each += copies the whole string (O(n^2) in total). "
                       "StringBuilder appends into a growing buffer."),
]
