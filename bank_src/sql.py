# Curated LeetCode database problems, solved in SQLite. `M`/`D` are injected by scripts/build_bank.py.
# Each problem: slug (LeetCode titleSlug), lc (frontend id), title, tier, schema (SQLite DDL list),
# summary (short paraphrase, HTML; the official statement is fetched from LeetCode at display time),
# datasets (D(...) list; the first `examples` are shown), ordered (row order matters?),
# solution (reference query; generates expected output), check {dataset_index: {"cols", "rows"}} (hand-verified),
# approach (one or two sentences shown after a bail-out).

PROBLEMS = [
    dict(
        slug="combine-two-tables", lc=175, title="Combine Two Tables", tier="easy",
        schema=["CREATE TABLE Person (personId INT, lastName VARCHAR(255), firstName VARCHAR(255))",
                "CREATE TABLE Address (addressId INT, personId INT, city VARCHAR(255), state VARCHAR(255))"],
        summary="<p>Report the <code>firstName, lastName, city, state</code> of every person in <code>Person</code>. "
                "If a person has no row in <code>Address</code>, report <code>null</code> for city and state. Any order.</p>",
        datasets=[
            D(Person=(["personId", "lastName", "firstName"], [[1, "Wang", "Allen"], [2, "Alice", "Bob"]]),
              Address=(["addressId", "personId", "city", "state"], [[1, 2, "New York City", "New York"], [2, 3, "Leetcode", "California"]])),
            D(Person=(["personId", "lastName", "firstName"], [[1, "Lovelace", "Ada"]]),
              Address=(["addressId", "personId", "city", "state"], [])),
            D(Person=(["personId", "lastName", "firstName"], [[1, "A", "B"], [2, "C", "D"], [3, "E", "F"]]),
              Address=(["addressId", "personId", "city", "state"], [[7, 3, "Austin", "Texas"], [8, 1, "Boise", "Idaho"]])),
        ],
        solution="SELECT p.firstName, p.lastName, a.city, a.state FROM Person p LEFT JOIN Address a ON a.personId = p.personId",
        check={0: {"cols": ["firstName", "lastName", "city", "state"],
                   "rows": [["Allen", "Wang", None, None], ["Bob", "Alice", "New York City", "New York"]]}},
        approach="LEFT JOIN Address onto Person so people without an address still appear, with NULLs.",
    ),

    # ------------------------------------------------------------------ easy
    dict(
        slug="employees-earning-more-than-their-managers", lc=181, title="Employees Earning More Than Their Managers",
        tier="easy",
        schema=["CREATE TABLE Employee (id INT, name VARCHAR(255), salary INT, managerId INT)"],
        summary="<p>Find every employee whose <code>salary</code> is strictly greater than the salary of their manager "
                "(the row whose <code>id</code> equals their <code>managerId</code>). Return one column, "
                "<code>Employee</code>, with their names. Any order.</p>",
        datasets=[
            D(Employee=(["id", "name", "salary", "managerId"],
                        [[1, "Joe", 70000, 3], [2, "Henry", 80000, 4], [3, "Sam", 60000, None], [4, "Max", 90000, None]])),
            D(Employee=(["id", "name", "salary", "managerId"],
                        [[1, "Ana", 50000, None], [2, "Ben", 40000, 1], [3, "Cy", 50000, 1]])),
            D(Employee=(["id", "name", "salary", "managerId"],
                        [[1, "Boss", 100, None], [2, "Mid", 150, 1], [3, "Low", 200, 2], [4, "Peer", 90, 1]])),
            D(Employee=(["id", "name", "salary", "managerId"],
                        [[1, "Orphan", 999, 42], [2, "Top", 10, None], [3, "Rich", 11, 2]])),
        ],
        solution="SELECT e.name AS Employee FROM Employee e JOIN Employee m ON m.id = e.managerId WHERE e.salary > m.salary",
        check={0: {"cols": ["Employee"], "rows": [["Joe"]]}},
        approach="Self-join Employee to itself on managerId = id, then keep rows where the employee out-earns the manager.",
    ),
    dict(
        slug="duplicate-emails", lc=182, title="Duplicate Emails", tier="easy",
        schema=["CREATE TABLE Person (id INT, email VARCHAR(255))"],
        summary="<p>Report every email that appears in more than one row of <code>Person</code>, once each, "
                "in a column named <code>Email</code>. Any order.</p>",
        datasets=[
            D(Person=(["id", "email"], [[1, "a@b.com"], [2, "c@d.com"], [3, "a@b.com"]])),
            D(Person=(["id", "email"], [[1, "one@x.com"], [2, "two@x.com"]])),
            D(Person=(["id", "email"], [[1, "x@y.com"], [2, "x@y.com"], [3, "x@y.com"], [4, "p@q.com"],
                                        [5, "p@q.com"], [6, "solo@z.com"]])),
        ],
        solution="SELECT email AS Email FROM Person GROUP BY email HAVING COUNT(*) > 1",
        check={0: {"cols": ["Email"], "rows": [["a@b.com"]]}},
        approach="GROUP BY email and keep the groups with HAVING COUNT(*) > 1.",
    ),
    dict(
        slug="customers-who-never-order", lc=183, title="Customers Who Never Order", tier="easy",
        schema=["CREATE TABLE Customers (id INT, name VARCHAR(255))",
                "CREATE TABLE Orders (id INT, customerId INT)"],
        summary="<p>List the names of customers who have no row in <code>Orders</code>, "
                "in a column named <code>Customers</code>. Any order.</p>",
        datasets=[
            D(Customers=(["id", "name"], [[1, "Joe"], [2, "Henry"], [3, "Sam"], [4, "Max"]]),
              Orders=(["id", "customerId"], [[1, 3], [2, 1]])),
            D(Customers=(["id", "name"], [[1, "Ann"], [2, "Bo"]]),
              Orders=(["id", "customerId"], [])),
            D(Customers=(["id", "name"], [[1, "Ann"], [2, "Bo"]]),
              Orders=(["id", "customerId"], [[1, 1], [2, 1], [3, 2]])),
            D(Customers=(["id", "name"], [[1, "Sam"], [2, "Sam"], [3, "Lee"]]),
              Orders=(["id", "customerId"], [[1, 1], [2, 3]])),
        ],
        solution="SELECT c.name AS Customers FROM Customers c "
                 "WHERE NOT EXISTS (SELECT 1 FROM Orders o WHERE o.customerId = c.id)",
        check={0: {"cols": ["Customers"], "rows": [["Henry"], ["Max"]]}},
        approach="Anti-join: keep customers for whom NOT EXISTS an order with their id (or LEFT JOIN and test for NULL).",
    ),
    dict(
        slug="big-countries", lc=595, title="Big Countries", tier="easy",
        schema=["CREATE TABLE World (name VARCHAR(255), continent VARCHAR(255), area INT, population INT, gdp BIGINT)"],
        summary="<p>A country is big if its <code>area</code> is at least 3,000,000 km&sup2; or its "
                "<code>population</code> is at least 25,000,000. Return <code>name, population, area</code> "
                "of the big countries. Any order.</p>",
        datasets=[
            D(World=(["name", "continent", "area", "population", "gdp"],
                     [["Afghanistan", "Asia", 652230, 25500100, 20343000000],
                      ["Albania", "Europe", 28748, 2831741, 12960000000],
                      ["Algeria", "Africa", 2381741, 37100000, 188681000000],
                      ["Andorra", "Europe", 468, 78115, 3712000000],
                      ["Angola", "Africa", 1246700, 20609294, 100990000000]])),
            D(World=(["name", "continent", "area", "population", "gdp"],
                     [["Edgeland", "Europe", 3000000, 1, 100], ["Popville", "Asia", 1, 25000000, 100],
                      ["Almost", "Africa", 2999999, 24999999, 100]])),
            D(World=(["name", "continent", "area", "population", "gdp"],
                     [["Russia", "Europe", 17098246, 144100000, 2240000000000],
                      ["Monaco", "Europe", 2, 39000, 7000000000]])),
            D(World=(["name", "continent", "area", "population", "gdp"],
                     [["Andorra", "Europe", 468, 78115, 3712000000]])),
        ],
        solution="SELECT name, population, area FROM World WHERE area >= 3000000 OR population >= 25000000",
        check={0: {"cols": ["name", "population", "area"],
                   "rows": [["Afghanistan", 25500100, 652230], ["Algeria", 37100000, 2381741]]}},
        approach="A plain WHERE with OR; note both thresholds are inclusive (>=).",
    ),
    dict(
        slug="find-customer-referee", lc=584, title="Find Customer Referee", tier="easy",
        schema=["CREATE TABLE Customer (id INT, name VARCHAR(25), referee_id INT)"],
        summary="<p>Return the <code>name</code> of every customer who was <em>not</em> referred by the customer "
                "with <code>id = 2</code>. Customers with no referee (<code>NULL</code>) count. Any order.</p>",
        datasets=[
            D(Customer=(["id", "name", "referee_id"],
                        [[1, "Will", None], [2, "Jane", None], [3, "Alex", 2], [4, "Bill", None], [5, "Zack", 1],
                         [6, "Mark", 2]])),
            D(Customer=(["id", "name", "referee_id"], [[1, "Ann", 2], [3, "Cat", 2]])),
            D(Customer=(["id", "name", "referee_id"], [[1, "A", None], [2, "B", None], [3, "C", None]])),
            D(Customer=(["id", "name", "referee_id"], [[1, "Kim", 3], [2, "Kim", 2], [3, "Kim", None]])),
        ],
        solution="SELECT name FROM Customer WHERE referee_id IS NULL OR referee_id <> 2",
        check={0: {"cols": ["name"], "rows": [["Will"], ["Jane"], ["Bill"], ["Zack"]]}},
        approach="referee_id <> 2 is UNKNOWN for NULL rows, so add an explicit OR referee_id IS NULL.",
    ),
    dict(
        slug="rising-temperature", lc=197, title="Rising Temperature", tier="easy",
        schema=["CREATE TABLE Weather (id INT, recordDate DATE, temperature INT)"],
        summary="<p>Return the <code>id</code> of every day whose <code>temperature</code> is higher than the "
                "temperature on the previous calendar day. Days without a record for the day before do not count. "
                "Any order.</p>",
        datasets=[
            D(Weather=(["id", "recordDate", "temperature"],
                       [[1, "2015-01-01", 10], [2, "2015-01-02", 25], [3, "2015-01-03", 20], [4, "2015-01-04", 30]])),
            D(Weather=(["id", "recordDate", "temperature"],
                       [[1, "2021-01-01", 20], [2, "2020-12-31", 10], [3, "2021-01-03", 30], [4, "2021-01-04", 25]])),
            D(Weather=(["id", "recordDate", "temperature"],
                       [[1, "2020-02-28", 5], [2, "2020-02-29", 5], [3, "2020-03-01", 6]])),
            D(Weather=(["id", "recordDate", "temperature"], [[1, "2019-07-01", 30]])),
        ],
        solution="SELECT w.id FROM Weather w JOIN Weather y ON DATEDIFF(w.recordDate, y.recordDate) = 1 "
                 "WHERE w.temperature > y.temperature",
        check={0: {"cols": ["id"], "rows": [[2], [4]]}},
        approach="Self-join each day to the row one calendar day earlier (DATEDIFF = 1), not to id - 1, then compare.",
    ),
    dict(
        slug="not-boring-movies", lc=620, title="Not Boring Movies", tier="easy",
        schema=["CREATE TABLE Cinema (id INT, movie VARCHAR(255), description VARCHAR(255), rating FLOAT(2, 1))"],
        summary="<p>Return all columns of the movies with an odd <code>id</code> whose <code>description</code> "
                "is not <code>'boring'</code>, ordered by <code>rating</code> descending.</p>",
        datasets=[
            D(Cinema=(["id", "movie", "description", "rating"],
                      [[1, "War", "great 3D", 8.9], [2, "Science", "fiction", 8.5], [3, "irish", "boring", 6.2],
                       [4, "Ice song", "Fantacy", 8.6], [5, "House card", "Interesting", 9.1]])),
            D(Cinema=(["id", "movie", "description", "rating"],
                      [[1, "Snooze", "boring", 5.0], [2, "Fun", "exciting", 9.9]])),
            D(Cinema=(["id", "movie", "description", "rating"],
                      [[1, "Hmm", "not boring", 7.5], [3, "Zzz", "boring", 9.9], [5, "Wow", "epic", 8.0],
                       [7, "Meh", "fine", 6.1], [8, "Even", "great", 9.5]])),
        ],
        ordered=True,
        solution="SELECT id, movie, description, rating FROM Cinema WHERE id % 2 = 1 AND description <> 'boring' "
                 "ORDER BY rating DESC",
        check={0: {"cols": ["id", "movie", "description", "rating"],
                   "rows": [[5, "House card", "Interesting", 9.1], [1, "War", "great 3D", 8.9]]}},
        approach="Filter with id % 2 = 1 and description <> 'boring', then ORDER BY rating DESC.",
    ),
    dict(
        slug="article-views-i", lc=1148, title="Article Views I", tier="easy",
        schema=["CREATE TABLE Views (article_id INT, author_id INT, viewer_id INT, view_date DATE)"],
        summary="<p>Find the authors who viewed at least one of their own articles (<code>author_id = viewer_id</code>). "
                "Return each one once, in a column named <code>id</code>, sorted ascending.</p>",
        datasets=[
            D(Views=(["article_id", "author_id", "viewer_id", "view_date"],
                     [[1, 3, 5, "2019-08-01"], [1, 3, 6, "2019-08-02"], [2, 7, 7, "2019-08-01"],
                      [2, 7, 6, "2019-08-02"], [4, 7, 1, "2019-07-22"], [3, 4, 4, "2019-07-21"],
                      [3, 4, 4, "2019-07-21"]])),
            D(Views=(["article_id", "author_id", "viewer_id", "view_date"],
                     [[1, 1, 2, "2020-01-01"], [2, 2, 1, "2020-01-02"]])),
            D(Views=(["article_id", "author_id", "viewer_id", "view_date"],
                     [[10, 9, 9, "2021-05-01"], [11, 9, 9, "2021-05-02"], [12, 3, 3, "2021-05-01"],
                      [13, 5, 6, "2021-05-03"]])),
        ],
        ordered=True,
        solution="SELECT DISTINCT author_id AS id FROM Views WHERE author_id = viewer_id ORDER BY id",
        check={0: {"cols": ["id"], "rows": [[4], [7]]}},
        approach="Keep rows where author_id = viewer_id, SELECT DISTINCT the author, ORDER BY id.",
    ),

    # ---------------------------------------------------------------- medium
    dict(
        slug="second-highest-salary", lc=176, title="Second Highest Salary", tier="medium",
        schema=["CREATE TABLE Employee (id INT, salary INT)"],
        summary="<p>Return the second highest <em>distinct</em> salary as a single row with one column, "
                "<code>SecondHighestSalary</code>. If there is no second highest salary, return one row "
                "containing <code>null</code>.</p>",
        datasets=[
            D(Employee=(["id", "salary"], [[1, 100], [2, 200], [3, 300]])),
            D(Employee=(["id", "salary"], [[1, 100]])),
            D(Employee=(["id", "salary"], [[1, 300], [2, 300], [3, 100]])),
            D(Employee=(["id", "salary"], [[1, 50], [2, 50]])),
            D(Employee=(["id", "salary"], [])),
        ],
        solution="SELECT (SELECT DISTINCT salary FROM Employee ORDER BY salary DESC LIMIT 1 OFFSET 1) "
                 "AS SecondHighestSalary",
        check={0: {"cols": ["SecondHighestSalary"], "rows": [[200]]},
               1: {"cols": ["SecondHighestSalary"], "rows": [[None]]}},
        approach="Wrap DISTINCT ... ORDER BY salary DESC LIMIT 1 OFFSET 1 in a scalar subquery; "
                 "an empty subquery becomes NULL, so you always get exactly one row.",
    ),
    dict(
        slug="rank-scores", lc=178, title="Rank Scores", tier="medium",
        schema=["CREATE TABLE Scores (id INT, score DECIMAL(3, 2))"],
        summary="<p>Rank the scores from highest to lowest. Equal scores share a rank, and the next rank is the next "
                "consecutive integer (no gaps). Return <code>score</code> and <code>rank</code>, ordered by "
                "<code>score</code> descending.</p>",
        datasets=[
            D(Scores=(["id", "score"], [[1, 3.50], [2, 3.65], [3, 4.00], [4, 3.85], [5, 4.00], [6, 3.65]])),
            D(Scores=(["id", "score"], [[1, 2.00], [2, 2.00]])),
            D(Scores=(["id", "score"], [[1, 0.00], [2, 5.00], [3, 4.99], [4, 4.99], [5, 0.01]])),
        ],
        ordered=True,
        solution='SELECT score, DENSE_RANK() OVER (ORDER BY score DESC) AS "rank" FROM Scores ORDER BY score DESC',
        check={0: {"cols": ["score", "rank"],
                   "rows": [[4.00, 1], [4.00, 1], [3.85, 2], [3.65, 3], [3.65, 3], [3.50, 4]]}},
        approach="DENSE_RANK() OVER (ORDER BY score DESC) gives gap-free ranks; quote the alias because rank is a "
                 "function name.",
    ),
    dict(
        slug="consecutive-numbers", lc=180, title="Consecutive Numbers", tier="medium",
        schema=["CREATE TABLE Logs (id INT, num INT)"],
        summary="<p><code>id</code> is an autoincrement column. Find every <code>num</code> that appears at least "
                "three times in a row (three consecutive ids). Return each one once, in a column named "
                "<code>ConsecutiveNums</code>. Any order.</p>",
        datasets=[
            D(Logs=(["id", "num"], [[1, 1], [2, 1], [3, 1], [4, 2], [5, 1], [6, 2], [7, 2]])),
            D(Logs=(["id", "num"], [[1, 1], [2, 2], [3, 1], [4, 2], [5, 1]])),
            D(Logs=(["id", "num"], [[1, 7], [2, 7], [3, 7], [4, 7], [5, 3], [6, 3], [7, 3]])),
            D(Logs=(["id", "num"], [[1, 5], [2, -1], [3, -1], [4, -1]])),
        ],
        solution="SELECT DISTINCT l1.num AS ConsecutiveNums FROM Logs l1 "
                 "JOIN Logs l2 ON l2.id = l1.id + 1 AND l2.num = l1.num "
                 "JOIN Logs l3 ON l3.id = l1.id + 2 AND l3.num = l1.num",
        check={0: {"cols": ["ConsecutiveNums"], "rows": [[1]]}},
        approach="Join Logs to itself at id + 1 and id + 2 with the same num (or compare LAG/LEAD), then DISTINCT.",
    ),
    dict(
        slug="department-highest-salary", lc=184, title="Department Highest Salary", tier="medium",
        schema=["CREATE TABLE Employee (id INT, name VARCHAR(255), salary INT, departmentId INT)",
                "CREATE TABLE Department (id INT, name VARCHAR(255))"],
        summary="<p>For each department, find the employees who have the highest salary in it (ties all count). "
                "Return <code>Department, Employee, Salary</code>. Any order.</p>",
        datasets=[
            D(Employee=(["id", "name", "salary", "departmentId"],
                        [[1, "Joe", 70000, 1], [2, "Jim", 90000, 1], [3, "Henry", 80000, 2], [4, "Sam", 60000, 2],
                         [5, "Max", 90000, 1]]),
              Department=(["id", "name"], [[1, "IT"], [2, "Sales"]])),
            D(Employee=(["id", "name", "salary", "departmentId"], [[1, "Ann", 500, 1]]),
              Department=(["id", "name"], [[1, "Ops"], [2, "Empty"]])),
            D(Employee=(["id", "name", "salary", "departmentId"],
                        [[1, "A", 10, 1], [2, "B", 10, 1], [3, "C", 10, 1], [4, "D", 5, 2], [5, "E", 7, 2],
                         [6, "F", 7, 3]]),
              Department=(["id", "name"], [[1, "X"], [2, "Y"], [3, "Z"]])),
            D(Employee=(["id", "name", "salary", "departmentId"],
                        [[1, "Hi", 900, 1], [2, "Trap", 300, 1], [3, "Mid", 300, 2], [4, "Lo", 100, 2]]),
              Department=(["id", "name"], [[1, "X"], [2, "Y"]])),
        ],
        solution="SELECT d.name AS Department, e.name AS Employee, e.salary AS Salary "
                 "FROM Employee e JOIN Department d ON d.id = e.departmentId "
                 "WHERE e.salary = (SELECT MAX(x.salary) FROM Employee x WHERE x.departmentId = e.departmentId)",
        check={0: {"cols": ["Department", "Employee", "Salary"],
                   "rows": [["IT", "Jim", 90000], ["Sales", "Henry", 80000], ["IT", "Max", 90000]]}},
        approach="Compare each salary to its own department's MAX (correlated subquery, or match on "
                 "(departmentId, MAX(salary)) pairs), then join Department for the name.",
    ),
    dict(
        slug="managers-with-at-least-5-direct-reports", lc=570, title="Managers with at Least 5 Direct Reports",
        tier="medium",
        schema=["CREATE TABLE Employee (id INT, name VARCHAR(255), department VARCHAR(255), managerId INT)"],
        summary="<p>Return the <code>name</code> of every manager who has at least five direct reports "
                "(rows whose <code>managerId</code> is the manager's <code>id</code>). Any order.</p>",
        datasets=[
            D(Employee=(["id", "name", "department", "managerId"],
                        [[101, "John", "A", None], [102, "Dan", "A", 101], [103, "James", "A", 101],
                         [104, "Amy", "A", 101], [105, "Anne", "A", 101], [106, "Ron", "B", 101]])),
            D(Employee=(["id", "name", "department", "managerId"],
                        [[1, "Boss", "A", None], [2, "a", "A", 1], [3, "b", "A", 1], [4, "c", "A", 1],
                         [5, "d", "A", 1]])),
            D(Employee=(["id", "name", "department", "managerId"],
                        [[10, "Real", "B", None], [11, "r1", "B", 10], [12, "r2", "B", 10], [13, "r3", "B", 10],
                         [14, "r4", "B", 10], [15, "r5", "B", 10], [16, "r6", "B", 10], [20, "g1", "C", 99],
                         [21, "g2", "C", 99], [22, "g3", "C", 99], [23, "g4", "C", 99], [24, "g5", "C", 99]])),
            D(Employee=(["id", "name", "department", "managerId"],
                        [[1, "Pat", "A", None], [2, "Pat", "B", None], [3, "a1", "A", 1], [4, "a2", "A", 1],
                         [5, "a3", "A", 1], [6, "a4", "A", 1], [7, "a5", "A", 1], [8, "b1", "B", 2],
                         [9, "b2", "B", 2], [10, "b3", "B", 2], [11, "b4", "B", 2], [12, "b5", "B", 2]])),
        ],
        solution="SELECT m.name FROM Employee m JOIN Employee r ON r.managerId = m.id "
                 "GROUP BY m.id, m.name HAVING COUNT(*) >= 5",
        check={0: {"cols": ["name"], "rows": [["John"]]}},
        approach="Join managers to their reports, GROUP BY the manager's id (not name), and keep COUNT(*) >= 5.",
    ),
    dict(
        slug="exchange-seats", lc=626, title="Exchange Seats", tier="medium",
        schema=["CREATE TABLE Seat (id INT, student VARCHAR(255))"],
        summary="<p>Swap the seat <code>id</code> of every two consecutive students (1&harr;2, 3&harr;4, ...). "
                "If the count is odd, the last student keeps their seat. Return <code>id, student</code> "
                "ordered by <code>id</code> ascending.</p>",
        datasets=[
            D(Seat=(["id", "student"], [[1, "Abbot"], [2, "Doris"], [3, "Emerson"], [4, "Green"], [5, "Jeames"]])),
            D(Seat=(["id", "student"], [[1, "Solo"]])),
            D(Seat=(["id", "student"], [[1, "A"], [2, "B"], [3, "C"], [4, "D"]])),
            D(Seat=(["id", "student"], [[3, "C"], [1, "A"], [2, "B"]])),
        ],
        ordered=True,
        solution="SELECT CASE WHEN id % 2 = 0 THEN id - 1 "
                 "WHEN id = (SELECT MAX(id) FROM Seat) THEN id ELSE id + 1 END AS id, student "
                 "FROM Seat ORDER BY 1",
        check={0: {"cols": ["id", "student"],
                   "rows": [[1, "Doris"], [2, "Abbot"], [3, "Green"], [4, "Emerson"], [5, "Jeames"]]}},
        approach="Rewrite the id instead of moving names: even ids go to id - 1, odd ids to id + 1 unless it is "
                 "the last (MAX) id. Then sort by the new id.",
    ),
    dict(
        slug="game-play-analysis-iv", lc=550, title="Game Play Analysis IV", tier="medium",
        schema=["CREATE TABLE Activity (player_id INT, device_id INT, event_date DATE, games_played INT)"],
        summary="<p>Report the fraction of players who logged in again on the day right after their "
                "<em>first</em> login, rounded to 2 decimal places, as a single column <code>fraction</code>.</p>"
                "<p><em>Grader note: this runs on SQLite, where integer / integer truncates (5 / 3 = 1). "
                "Multiply by 1.0 before you divide.</em></p>",
        datasets=[
            D(Activity=(["player_id", "device_id", "event_date", "games_played"],
                        [[1, 2, "2016-03-01", 5], [1, 2, "2016-03-02", 6], [2, 3, "2017-06-25", 1],
                         [3, 1, "2016-03-02", 0], [3, 4, "2018-07-03", 5]])),
            D(Activity=(["player_id", "device_id", "event_date", "games_played"],
                        [[1, 1, "2020-01-31", 1], [1, 1, "2020-02-01", 2], [2, 1, "2020-12-31", 1],
                         [2, 2, "2021-01-01", 0]])),
            D(Activity=(["player_id", "device_id", "event_date", "games_played"],
                        [[1, 1, "2021-03-01", 1], [1, 1, "2021-03-05", 1], [1, 1, "2021-03-06", 1],
                         [2, 3, "2021-03-02", 4]])),
            D(Activity=(["player_id", "device_id", "event_date", "games_played"],
                        [[1, 1, "2024-02-28", 1], [1, 1, "2024-02-29", 1], [2, 1, "2024-02-28", 1],
                         [2, 1, "2024-03-01", 1], [3, 2, "2024-02-29", 3], [3, 2, "2024-03-01", 1]])),
        ],
        solution="SELECT ROUND(COUNT(a.player_id) * 1.0 / COUNT(*), 2) AS fraction "
                 "FROM (SELECT player_id, MIN(event_date) AS first_day FROM Activity GROUP BY player_id) f "
                 "LEFT JOIN Activity a ON a.player_id = f.player_id AND DATEDIFF(a.event_date, f.first_day) = 1",
        check={0: {"cols": ["fraction"], "rows": [[0.33]]}},
        approach="Find each player's MIN(event_date), LEFT JOIN to a login exactly one day later, and divide the "
                 "matches by the number of players.",
    ),
    dict(
        slug="capital-gainloss", lc=1393, title="Capital Gain/Loss", tier="medium",
        schema=["CREATE TABLE Stocks (stock_name VARCHAR(15), operation VARCHAR(4), operation_day INT, price INT)"],
        summary="<p>Every <code>'Buy'</code> of a stock is later matched by a <code>'Sell'</code>. Report each "
                "stock's total capital gain or loss (sell prices minus buy prices) as "
                "<code>stock_name, capital_gain</code>. Any order.</p>",
        datasets=[
            D(Stocks=(["stock_name", "operation", "operation_day", "price"],
                      [["Leetcode", "Buy", 1, 1000], ["Corona Masks", "Buy", 2, 10], ["Leetcode", "Sell", 5, 9000],
                       ["Handbags", "Buy", 17, 30000], ["Corona Masks", "Sell", 3, 1010],
                       ["Corona Masks", "Buy", 4, 1000], ["Corona Masks", "Sell", 5, 500],
                       ["Corona Masks", "Buy", 6, 1000], ["Handbags", "Sell", 29, 7000],
                       ["Corona Masks", "Sell", 10, 10000]])),
            D(Stocks=(["stock_name", "operation", "operation_day", "price"],
                      [["Flat", "Buy", 1, 100], ["Flat", "Sell", 2, 100]])),
            D(Stocks=(["stock_name", "operation", "operation_day", "price"],
                      [["Zeta", "Sell", 9, 50], ["Zeta", "Buy", 3, 80], ["Alpha", "Buy", 1, 5],
                       ["Alpha", "Sell", 2, 15], ["Alpha", "Buy", 4, 20], ["Alpha", "Sell", 6, 40],
                       ["Zeta", "Buy", 10, 10], ["Zeta", "Sell", 12, 100]])),
        ],
        solution="SELECT stock_name, SUM(CASE WHEN operation = 'Sell' THEN price ELSE -price END) AS capital_gain "
                 "FROM Stocks GROUP BY stock_name",
        check={0: {"cols": ["stock_name", "capital_gain"],
                   "rows": [["Corona Masks", 9500], ["Leetcode", 8000], ["Handbags", -23000]]}},
        approach="Pairing buys and sells is unnecessary: SUM(price) with buys negated, GROUP BY stock_name.",
    ),

    # ------------------------------------------------------------------ hard
    dict(
        slug="department-top-three-salaries", lc=185, title="Department Top Three Salaries", tier="hard",
        schema=["CREATE TABLE Employee (id INT, name VARCHAR(255), salary INT, departmentId INT)",
                "CREATE TABLE Department (id INT, name VARCHAR(255))"],
        summary="<p>A high earner is an employee whose salary is among the top three <em>distinct</em> salaries of "
                "their department. Return <code>Department, Employee, Salary</code> for all high earners. "
                "Any order.</p>",
        datasets=[
            D(Employee=(["id", "name", "salary", "departmentId"],
                        [[1, "Joe", 85000, 1], [2, "Henry", 80000, 2], [3, "Sam", 60000, 2], [4, "Max", 90000, 1],
                         [5, "Janet", 69000, 1], [6, "Randy", 85000, 1], [7, "Will", 70000, 1]]),
              Department=(["id", "name"], [[1, "IT"], [2, "Sales"]])),
            D(Employee=(["id", "name", "salary", "departmentId"],
                        [[1, "A", 100, 1], [2, "B", 100, 1], [3, "C", 50, 1], [4, "D", 70, 2]]),
              Department=(["id", "name"], [[1, "Eng"], [2, "Ops"]])),
            D(Employee=(["id", "name", "salary", "departmentId"],
                        [[1, "P", 90, 1], [2, "Q", 90, 1], [3, "R", 80, 1], [4, "S", 80, 1], [5, "T", 70, 1],
                         [6, "U", 60, 1]]),
              Department=(["id", "name"], [[1, "Lab"], [3, "Ghost"]])),
            D(Employee=(["id", "name", "salary", "departmentId"],
                        [[1, "A", 300, 1], [2, "B", 200, 1], [3, "C", 100, 1], [4, "D", 50, 1], [5, "E", 400, 2],
                         [6, "F", 350, 2], [7, "G", 330, 2], [8, "H", 50, 2]]),
              Department=(["id", "name"], [[1, "Red"], [2, "Blue"]])),
        ],
        solution="SELECT d.name AS Department, e.name AS Employee, e.salary AS Salary "
                 "FROM (SELECT *, DENSE_RANK() OVER (PARTITION BY departmentId ORDER BY salary DESC) AS rk "
                 "FROM Employee) e JOIN Department d ON d.id = e.departmentId WHERE e.rk <= 3",
        check={0: {"cols": ["Department", "Employee", "Salary"],
                   "rows": [["IT", "Max", 90000], ["IT", "Joe", 85000], ["IT", "Randy", 85000],
                            ["IT", "Will", 70000], ["Sales", "Henry", 80000], ["Sales", "Sam", 60000]]}},
        approach="DENSE_RANK() OVER (PARTITION BY departmentId ORDER BY salary DESC) and keep rank <= 3; or count "
                 "the distinct higher salaries in the same department and keep counts < 3.",
    ),
    dict(
        slug="trips-and-users", lc=262, title="Trips and Users", tier="hard",
        schema=["CREATE TABLE Trips (id INT, client_id INT, driver_id INT, city_id INT, status VARCHAR(32), "
                "request_at VARCHAR(50))",
                "CREATE TABLE Users (users_id INT, banned VARCHAR(50), role VARCHAR(16))"],
        summary="<p>For each day from <code>2013-10-01</code> to <code>2013-10-03</code>, compute the cancellation "
                "rate: cancelled requests (by client or driver) divided by all requests, counting only trips whose "
                "client and driver are both unbanned. Round to 2 decimals. Return <code>Day</code> and "
                "<code>Cancellation Rate</code>; skip days with no such trips. Any order.</p>"
                "<p><em>Grader note: this runs on SQLite, where integer / integer truncates (5 / 3 = 1). "
                "Multiply by 1.0 before you divide.</em></p>",
        datasets=[
            D(Trips=(["id", "client_id", "driver_id", "city_id", "status", "request_at"],
                     [[1, 1, 10, 1, "completed", "2013-10-01"], [2, 2, 11, 1, "cancelled_by_driver", "2013-10-01"],
                      [3, 3, 12, 6, "completed", "2013-10-01"], [4, 4, 13, 6, "cancelled_by_client", "2013-10-01"],
                      [5, 1, 10, 1, "completed", "2013-10-02"], [6, 2, 11, 6, "completed", "2013-10-02"],
                      [7, 3, 12, 6, "completed", "2013-10-02"], [8, 2, 12, 12, "completed", "2013-10-03"],
                      [9, 3, 10, 12, "completed", "2013-10-03"],
                      [10, 4, 13, 12, "cancelled_by_driver", "2013-10-03"]]),
              Users=(["users_id", "banned", "role"],
                     [[1, "No", "client"], [2, "Yes", "client"], [3, "No", "client"], [4, "No", "client"],
                      [10, "No", "driver"], [11, "No", "driver"], [12, "No", "driver"], [13, "No", "driver"]])),
            D(Trips=(["id", "client_id", "driver_id", "city_id", "status", "request_at"],
                     [[1, 1, 20, 1, "cancelled_by_client", "2013-09-30"], [2, 1, 20, 1, "completed", "2013-10-01"],
                      [3, 2, 21, 1, "cancelled_by_driver", "2013-10-01"], [4, 2, 21, 1, "completed", "2013-10-02"],
                      [5, 2, 20, 1, "cancelled_by_driver", "2013-10-03"], [6, 1, 20, 1, "completed", "2013-10-04"]]),
              Users=(["users_id", "banned", "role"],
                     [[1, "No", "client"], [2, "No", "client"], [20, "No", "driver"], [21, "Yes", "driver"]])),
            D(Trips=(["id", "client_id", "driver_id", "city_id", "status", "request_at"],
                     [[1, 1, 10, 1, "cancelled_by_driver", "2013-10-02"], [2, 2, 11, 1, "cancelled_by_client", "2013-10-02"],
                      [3, 3, 10, 1, "completed", "2013-10-02"]]),
              Users=(["users_id", "banned", "role"],
                     [[1, "No", "client"], [2, "No", "client"], [3, "No", "client"], [10, "No", "driver"],
                      [11, "No", "driver"]])),
            D(Trips=(["id", "client_id", "driver_id", "city_id", "status", "request_at"],
                     [[1, 1, 10, 1, "completed", "2013-11-01"]]),
              Users=(["users_id", "banned", "role"], [[1, "No", "client"], [10, "No", "driver"]])),
        ],
        solution="SELECT t.request_at AS Day, "
                 "ROUND(AVG(CASE WHEN t.status = 'completed' THEN 0.0 ELSE 1.0 END), 2) AS \"Cancellation Rate\" "
                 "FROM Trips t "
                 "JOIN Users c ON c.users_id = t.client_id AND c.banned = 'No' "
                 "JOIN Users d ON d.users_id = t.driver_id AND d.banned = 'No' "
                 "WHERE t.request_at BETWEEN '2013-10-01' AND '2013-10-03' "
                 "GROUP BY t.request_at",
        check={0: {"cols": ["Day", "Cancellation Rate"],
                   "rows": [["2013-10-01", 0.33], ["2013-10-02", 0.00], ["2013-10-03", 0.50]]}},
        approach="Join Users twice (client and driver) with banned = 'No', filter the date range, GROUP BY day, and "
                 "average a 1/0 cancelled flag.",
    ),
    dict(
        slug="human-traffic-of-stadium", lc=601, title="Human Traffic of Stadium", tier="hard",
        schema=["CREATE TABLE Stadium (id INT, visit_date DATE, people INT)"],
        summary="<p>Return every row that belongs to a run of three or more consecutive <code>id</code>s in which "
                "each row has <code>people &gt;= 100</code>. Return <code>id, visit_date, people</code> ordered by "
                "<code>visit_date</code> ascending.</p>",
        datasets=[
            D(Stadium=(["id", "visit_date", "people"],
                       [[1, "2017-01-01", 10], [2, "2017-01-02", 109], [3, "2017-01-03", 150], [4, "2017-01-04", 99],
                        [5, "2017-01-05", 145], [6, "2017-01-06", 1455], [7, "2017-01-07", 199],
                        [8, "2017-01-09", 188]])),
            D(Stadium=(["id", "visit_date", "people"],
                       [[1, "2020-01-01", 100], [2, "2020-01-02", 100], [3, "2020-01-03", 99], [4, "2020-01-04", 500],
                        [5, "2020-01-05", 500]])),
            D(Stadium=(["id", "visit_date", "people"],
                       [[1, "2021-06-01", 100], [2, "2021-06-02", 100], [3, "2021-06-03", 100], [4, "2021-06-04", 5],
                        [5, "2021-06-05", 200], [6, "2021-06-06", 300], [7, "2021-06-07", 50],
                        [8, "2021-06-08", 120], [9, "2021-06-09", 130], [10, "2021-06-10", 140],
                        [11, "2021-06-11", 150]])),
            D(Stadium=(["id", "visit_date", "people"],
                       [[1, "2017-03-01", 1000], [2, "2017-03-05", 1000], [3, "2017-03-09", 1000]])),
        ],
        ordered=True,
        solution="WITH good AS (SELECT id, visit_date, people, id - ROW_NUMBER() OVER (ORDER BY id) AS grp "
                 "FROM Stadium WHERE people >= 100), "
                 "sized AS (SELECT *, COUNT(*) OVER (PARTITION BY grp) AS n FROM good) "
                 "SELECT id, visit_date, people FROM sized WHERE n >= 3 ORDER BY visit_date",
        check={0: {"cols": ["id", "visit_date", "people"],
                   "rows": [[5, "2017-01-05", 145], [6, "2017-01-06", 1455], [7, "2017-01-07", 199],
                            [8, "2017-01-09", 188]]}},
        approach="Gaps and islands: among rows with people >= 100, id - ROW_NUMBER() is constant within each run "
                 "of consecutive ids. Keep the groups of size >= 3.",
    ),
]
