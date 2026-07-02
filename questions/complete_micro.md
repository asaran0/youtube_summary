# Phase 1: Microservices Fundamentals Interview Questions and Answers

## Topic 1: What are Microservices?

Q1: What are Microservices? (Asked in TCS, Infosys, Capgemini, Cognizant, Wipro, Accenture, EPAM)

A:
Microservices are an architectural style where an application is divided into multiple small, independent services. Each service focuses on a specific business capability and can be developed, deployed, and scaled independently.

For example, in an e-commerce application, we can have separate services for:

* User Service
* Product Service
* Order Service
* Payment Service
* Notification Service

Each service has its own codebase, database, and deployment process. These services communicate with each other using APIs such as REST or messaging systems like Kafka.

In simple words, instead of building one large application, we build several small applications that work together.

---

Q2: Why are microservices called loosely coupled services? (Asked in TCS, HCL, Infosys, EPAM)

A:
Microservices are called loosely coupled because each service works independently and has minimal dependency on other services.

For example:

Order Service needs customer information.

Instead of directly accessing the Customer Service database, it calls the Customer Service API.

If Customer Service changes its database design, Order Service usually does not need modification as long as the API remains the same.

Loose coupling provides:

* Easier maintenance
* Independent deployment
* Better scalability
* Reduced impact of changes

This is one of the biggest advantages of microservices.

---

Q3: What is a business capability in microservices? (Asked in Accenture, Capgemini, Cognizant)

A:
A business capability is a specific business function that provides a particular feature to users.

Examples:

* User Registration
* Product Management
* Order Processing
* Payment Handling
* Inventory Management

Each microservice should ideally represent one business capability.

For example:

Payment Service should only manage:

* Payment creation
* Payment status
* Refund processing

It should not contain product management or inventory logic.

This principle keeps services focused and easy to maintain.

---

Q4: How do microservices communicate with each other? (Asked in TCS, Infosys, EPAM, IBM)

A:
Microservices communicate using APIs and messaging systems.

There are mainly two ways:

1. Synchronous Communication
   Examples:

* REST API
* gRPC

Example:
Order Service calls Payment Service and waits for a response.

2. Asynchronous Communication
   Examples:

* Kafka
* RabbitMQ

Example:
Order Service publishes an event saying:

"Order Created"

Inventory Service and Notification Service receive the event and perform their work independently.

Asynchronous communication provides better scalability and lower coupling.

---

Q5: Can microservices use different technologies? (Asked in Wipro, Accenture, Cognizant)

A:
Yes.

One of the advantages of microservices is technology diversity.

For example:

* User Service may use Java and Spring Boot.
* Recommendation Service may use Python.
* Notification Service may use Node.js.

All services can still communicate through APIs.

This allows teams to choose the best technology for their business requirements.

However, companies should avoid unnecessary technology diversity because maintaining too many technologies increases operational complexity.

---

Q6: What are the main principles of microservices architecture? (Asked in EPAM, Capgemini, Infosys)

A:
The main principles are:

* Single Responsibility
* Independent Deployment
* Loose Coupling
* High Cohesion
* Decentralized Data Management
* Fault Isolation
* Independent Scaling
* Automation and Continuous Delivery

Example:

During a festive sale:

* Product Service may receive heavy traffic.
* Payment Service traffic may remain normal.

Only Product Service can be scaled instead of scaling the entire application.

This makes the system more efficient and cost-effective.

---

## Topic 2: Monolithic vs Microservices Architecture

Q7: What is a Monolithic Architecture? (Asked in TCS, Infosys, HCL, Capgemini)

A:
Monolithic architecture is a software architecture where the entire application is developed and deployed as a single unit.

For example, an e-commerce application may contain:

* User Module
* Product Module
* Order Module
* Payment Module

All modules exist inside one application and share the same database.

A small change in one module generally requires redeploying the entire application.

Monolithic architecture is simple initially but becomes difficult to manage as the application grows.

---

Q8: What is the difference between Monolithic and Microservices Architecture? (Asked in TCS, Infosys, EPAM, Accenture)

A:

Monolithic Architecture:

* Single application
* Single deployment
* Usually one database
* Entire application scales together
* Technology stack is usually fixed
* Failure can impact the entire system

Microservices Architecture:

* Multiple independent services
* Independent deployment
* Database per service
* Services can scale individually
* Different technologies can be used
* Better fault isolation

Example:

Suppose Product Search receives heavy traffic.

In Monolithic Architecture:
Entire application must be scaled.

In Microservices Architecture:
Only Product Service needs additional instances.

This reduces infrastructure cost significantly.

---

Q9: Why do companies move from monolith to microservices? (Asked in Amazon, Microsoft, TCS, EPAM, Infosys)

A:
Companies usually move to microservices because monolithic applications become difficult to manage as they grow.

Problems with large monoliths:

* Slow deployments
* Large codebase
* Difficult maintenance
* Poor scalability
* Team dependencies
* Higher risk during releases

Example:

A change in Payment Module may require redeploying the entire application, including User and Product modules.

In microservices:
Only Payment Service is deployed.

This allows:

* Faster releases
* Better scalability
* Independent teams
* Improved reliability

However, companies should move to microservices only when business complexity justifies it.

---

Q10: When should you not use microservices? (Asked in EPAM, Accenture, IBM, Capgemini)

A:
Microservices should not be used when:

* The application is small.
* Team size is small.
* Requirements are simple.
* Traffic is low.
* Deployment frequency is low.
* Team lacks distributed system experience.

Example:

A simple employee leave management system with only a few modules may not need microservices.

Using microservices in such cases can create unnecessary complexity:

* Multiple deployments
* API management
* Monitoring
* Service communication
* Distributed debugging

Sometimes a well-designed monolithic application is a better solution.

This answer is appreciated by interviewers because it shows that microservices are not always the correct choice.

---

Q11: What problems do microservices solve? (Asked in TCS, Infosys, Wipro, Cognizant)

A:
Microservices solve several problems found in large monolithic applications.

Problems solved:

* Independent deployment
* Better scalability
* Faster development
* Team autonomy
* Fault isolation
* Easier maintenance
* Technology flexibility

Example:

Suppose Notification Service has a bug.

In monolithic architecture:
Entire application may need redeployment.

In microservices:
Only Notification Service is fixed and deployed.

This reduces downtime and risk.

---

Q12: Are microservices always better than monolithic architecture? (Asked in Amazon, EPAM, IBM)

A:
No.

Microservices are not always better.

Monolithic architecture is often better when:

* Product is in early stages
* Team is small
* Requirements are simple
* Traffic is low
* Faster initial development is needed

Microservices are beneficial when:

* Application becomes large
* Teams become bigger
* Deployment frequency increases
* Scalability requirements become high
* Business domains become complex

The right architecture depends on business requirements and not on industry trends.

Interviewers generally like this answer because it demonstrates practical architectural thinking rather than blindly preferring microservices.


# Phase 1 - Part 2: Characteristics, Advantages and Disadvantages of Microservices

## Topic 3: Characteristics of Microservices

Q13: What are the main characteristics of Microservices Architecture? (Asked in TCS, Infosys, EPAM, Cognizant, Accenture)

A:
The main characteristics of microservices are:

* Small and focused services
* Single business capability
* Independent deployment
* Loose coupling
* High cohesion
* Database per service
* Independent scaling
* Fault isolation
* Decentralized governance
* Technology diversity
* Automation and continuous delivery

Example:

In an e-commerce application:

* User Service manages users.
* Product Service manages products.
* Order Service manages orders.
* Payment Service manages payments.

Each service focuses on only one responsibility and can be developed and deployed independently.

This separation makes the system easier to maintain and scale.

---

Q14: What does "Single Responsibility" mean in Microservices? (Asked in TCS, HCL, Infosys)

A:
Single Responsibility means one service should handle only one business capability.

Example:

Payment Service should handle:

* Payment processing
* Payment status
* Refund management

It should not manage:

* Product information
* User registration
* Inventory management

Benefits:

* Easier maintenance
* Smaller codebase
* Independent deployment
* Reduced complexity

A good microservice should have one reason to change.

---

Q15: What is meant by High Cohesion in Microservices? (Asked in EPAM, Accenture, IBM)

A:
High cohesion means all functionalities inside a service should be closely related and belong to the same business capability.

Example:

Order Service should contain:

* Create Order
* Update Order
* Cancel Order
* Order Status

All these operations are related to order management.

It should not contain:

* Email sending
* User authentication
* Product recommendations

Keeping related functionalities together makes services easier to understand and maintain.

---

Q16: What is Loose Coupling in Microservices? (Asked in TCS, Infosys, Capgemini)

A:
Loose coupling means services should have minimal dependency on each other.

Example:

Order Service needs payment information.

Good approach:
Order Service calls Payment Service API.

Bad approach:
Order Service directly accesses Payment Service database.

Direct database access creates strong dependency and makes maintenance difficult.

Loose coupling provides:

* Easier changes
* Independent deployments
* Better maintainability
* Better fault isolation

---

Q17: What is Independent Deployment in Microservices? (Asked in Amazon, EPAM, TCS)

A:
Independent deployment means each service can be deployed separately without redeploying the entire application.

Example:

A bug is found in Notification Service.

In Monolithic Architecture:
Entire application needs redeployment.

In Microservices:
Only Notification Service is deployed.

Benefits:

* Faster releases
* Lower deployment risk
* Smaller downtime
* Better productivity

This is one of the biggest reasons organizations adopt microservices.

---

Q18: What is Independent Scaling in Microservices? (Asked in Infosys, Accenture, Wipro)

A:
Independent scaling means only the service experiencing high traffic is scaled.

Example:

During a sale:

* Product Service receives 50,000 requests per minute.
* Payment Service receives only 5,000 requests.

Instead of scaling the whole application, only Product Service gets additional instances.

Benefits:

* Lower infrastructure cost
* Better resource utilization
* Improved performance

This is much more efficient than monolithic scaling.

---

Q19: What is Fault Isolation in Microservices? (Asked in Amazon, EPAM, IBM)

A:
Fault isolation means failure of one service should not bring down the entire system.

Example:

Notification Service crashes.

Ideally:

* Users should still browse products.
* Orders should still be placed.
* Payments should still work.

Only notifications may be delayed.

Benefits:

* Improved availability
* Better user experience
* Reduced impact of failures

Fault isolation is extremely important in distributed systems.

---

Q20: What is Technology Diversity in Microservices? (Asked in Accenture, Cognizant, Capgemini)

A:
Technology diversity means different services can use different technologies.

Example:

* User Service → Java and Spring Boot
* Recommendation Service → Python
* Notification Service → Node.js

Every service uses the technology that best suits its requirements.

Advantages:

* Flexibility
* Better productivity
* Ability to use specialized technologies

Disadvantage:
Too many technologies can increase maintenance complexity.

Good companies balance flexibility with standardization.

---

## Topic 4: Advantages of Microservices

Q21: What are the advantages of Microservices Architecture? (Asked in TCS, Infosys, Wipro, EPAM)

A:
Major advantages are:

* Independent deployment
* Independent scaling
* Better fault isolation
* Faster development
* Smaller codebase
* Team autonomy
* Technology flexibility
* Easier maintenance
* Faster releases
* Better resource utilization

Example:

Suppose a company has separate teams for:

* User Management
* Orders
* Payments
* Notifications

Each team can work independently and release features without waiting for other teams.

This significantly increases development speed.

---

Q22: How do microservices improve scalability? (Asked in Amazon, Microsoft, EPAM)

A:
Microservices improve scalability by allowing services to scale independently.

Example:

An online shopping application has:

Product Service:
100,000 requests per minute

Payment Service:
10,000 requests per minute

Only Product Service needs additional servers.

Benefits:

* Lower cloud cost
* Better performance
* Efficient resource usage

In monolithic systems, the entire application would need scaling, even if only one module is busy.

---

Q23: How do microservices help large development teams? (Asked in Infosys, Capgemini, Cognizant)

A:
Microservices allow teams to work independently.

Example:

Team A:
User Service

Team B:
Order Service

Team C:
Payment Service

Each team:

* Owns its service
* Maintains its code
* Deploys independently
* Makes decisions faster

Benefits:

* Reduced dependencies
* Faster releases
* Better productivity

Large organizations like Amazon use this model extensively.

---

## Topic 5: Disadvantages of Microservices

Q24: What are the disadvantages of Microservices Architecture? (Asked in TCS, Infosys, HCL, Accenture)

A:
Major disadvantages are:

* Higher architectural complexity
* Distributed system challenges
* Difficult debugging
* Network latency
* Data consistency problems
* More infrastructure requirements
* Monitoring complexity
* Deployment complexity
* Testing complexity
* Higher operational cost

Microservices solve many problems but also introduce new challenges.

This is why they should be adopted only when business requirements justify them.

---

Q25: Why are microservices difficult to debug? (Asked in EPAM, IBM, Amazon)

A:
In monolithic applications, logs are usually present in one application.

In microservices:

One user request may pass through:

API Gateway
→ User Service
→ Order Service
→ Payment Service
→ Notification Service

If an issue occurs, developers need logs from multiple services.

Challenges:

* Distributed logs
* Multiple deployments
* Multiple databases
* Network failures

Therefore, tools like distributed tracing and centralized logging become necessary.

---

Q26: Why can microservices increase infrastructure costs? (Asked in Accenture, Wipro, Cognizant)

A:
Each service may require:

* Separate deployment
* Database
* Monitoring
* Logging
* Containers
* CI/CD pipeline

Example:

A monolithic application may run on three servers.

The same system may require:

* Multiple containers
* Databases
* Monitoring tools
* Message brokers
* API gateways

This increases operational costs.

Microservices improve scalability and flexibility, but infrastructure management becomes more expensive.

---

Q27: Why do microservices have network latency issues? (Asked in Amazon, EPAM, IBM)

A:
In monolithic applications, method calls happen inside the same process.

Example:

orderService.getPaymentStatus();

Execution is extremely fast.

In microservices:

Order Service
calls
Payment Service API over the network.

Network communication introduces:

* Serialization
* Deserialization
* Network delay
* Retries
* Timeouts

Therefore, remote service calls are always slower than in-process method calls.

Interview Tip:
Always remember this sentence:

"In microservices, every network call can fail, become slow, or time out."

Interviewers particularly like this answer because it shows understanding of distributed systems.

---

Q28: What is the biggest mistake companies make while adopting microservices? (Asked in Amazon, EPAM, Microsoft)

A:
The biggest mistake is adopting microservices too early.

Example:

A startup with:

* Five developers
* Simple application
* Few users

Usually does not need:

* API Gateway
* Service discovery
* Message brokers
* Distributed tracing
* Multiple databases

Introducing microservices too early creates unnecessary complexity.

A better approach is:

Start with a modular monolith.
Move to microservices only when:

* Business grows
* Teams grow
* Deployment frequency increases
* Scalability requirements become high

This answer demonstrates practical architectural maturity and is highly appreciated by interviewers.


# Phase 1 - Part 3: Bounded Context, DDD Basics, Database per Service Pattern, and Stateless Services

## Topic 6: Bounded Context and Domain-Driven Design (DDD) Basics

Q29: What is Domain-Driven Design (DDD)? (Asked in Amazon, EPAM, Microsoft, Infosys, TCS)

A:
Domain-Driven Design, or DDD, is a software design approach that focuses on understanding the business domain first and then designing software around business concepts.

Simply put:

"First understand how the business works, then design the software."

Example:

Suppose we are building an e-commerce application.

Business domains may be:

* User Management
* Product Management
* Order Management
* Payment Management
* Shipping Management

Instead of creating one huge application containing everything, DDD encourages us to identify business domains and design services around them.

Benefits:

* Better business understanding
* Better software design
* Easier maintenance
* Natural fit for microservices

---

Q30: What is a Domain in DDD? (Asked in Infosys, TCS, Cognizant)

A:
A domain is the business area for which software is being developed.

Examples:

Banking System:

* Customer Domain
* Account Domain
* Loan Domain
* Payment Domain

E-commerce System:

* Product Domain
* Order Domain
* Inventory Domain
* Payment Domain

Every domain solves a specific business problem.

In microservices, services are usually designed around domains.

---

Q31: What is a Bounded Context? (Asked in Amazon, EPAM, Microsoft, Capgemini)

A:
A bounded context is a clearly defined boundary within which a business model and terminology have specific meaning.

Simple definition:

"A bounded context defines what a service owns and what it does not own."

Example:

The word "Order" can have different meanings.

Order Service:

* Order ID
* Order Items
* Order Status

Shipping Service:

* Delivery Address
* Shipment Status
* Tracking Number

Both services use the word "Order," but their responsibilities are different.

Bounded context creates clear ownership and avoids confusion.

---

Q32: Why is Bounded Context important in Microservices? (Asked in EPAM, Amazon, IBM)

A:
Without bounded context:

* Services overlap
* Responsibilities become unclear
* Teams modify each other's data
* Changes become risky

Example:

Suppose both Order Service and Payment Service manage payment information.

Questions arise:

* Which service owns payment status?
* Which service updates refunds?
* Which service becomes the source of truth?

This confusion creates maintenance problems.

Bounded context solves this by assigning clear ownership.

Payment Service owns:

* Payment Status
* Refunds
* Transactions

Order Service only consumes payment information through APIs.

---

Q33: How does DDD help in designing Microservices? (Asked in Amazon, EPAM, Accenture)

A:
DDD helps identify natural service boundaries.

Example:

Without DDD:
Developers may split services based on technical layers.

* Controller Service
* Repository Service
* Database Service

This is usually incorrect.

With DDD:
Services are divided according to business capabilities.

* User Service
* Product Service
* Order Service
* Payment Service

Benefits:

* Better business alignment
* Clear ownership
* Lower coupling
* Easier maintenance

This is why DDD and microservices are often used together.

---

Q34: Can one Microservice have multiple business responsibilities? (Asked in TCS, Infosys, HCL)

A:
Ideally, no.

A microservice should focus on one business capability.

Bad example:

Customer Service handles:

* Customer Management
* Orders
* Payments
* Inventory

This service becomes very large and difficult to maintain.

Good design:

Customer Service
Order Service
Payment Service
Inventory Service

Each service has a clear responsibility.

This follows both:

* Single Responsibility Principle
* Bounded Context Principle

---

## Topic 7: Database per Service Pattern

Q35: What is the Database per Service Pattern? (Asked in Amazon, EPAM, Infosys, Capgemini)

A:
Database per Service means every microservice owns its own database.

Example:

User Service
→ User Database

Order Service
→ Order Database

Payment Service
→ Payment Database

Services never directly access another service's database.

Communication happens only through APIs or events.

This pattern is one of the fundamental principles of microservices architecture.

---

Q36: Why should each Microservice have its own database? (Asked in TCS, Infosys, Accenture)

A:
Having separate databases provides:

* Loose coupling
* Independent deployment
* Independent scaling
* Better security
* Clear ownership

Example:

If Order Service directly accesses Payment Database:

Problems:

* Strong dependency
* Database schema changes break services
* Difficult maintenance

If Payment Service owns its database:

Order Service simply calls:

GET /payment/status

Both services remain independent.

---

Q37: Can two Microservices share the same database? (Asked in Amazon, EPAM, IBM)

A:
Technically yes.

Architecturally, it is usually considered a bad practice.

Example:

Order Service and Payment Service share one database.

Problems:

* Tight coupling
* Schema dependency
* Difficult deployments
* Difficult scaling
* Ownership confusion

If Payment table changes, Order Service may break.

Interview Tip:

A shared database often indicates that the services are not truly independent microservices.

---

Q38: How do Microservices get data from other services if databases are separate? (Asked in TCS, Infosys, Cognizant)

A:
Services obtain data using:

1. REST APIs
2. gRPC
3. Messaging systems like Kafka or RabbitMQ

Example:

Order Service needs payment status.

Bad approach:

SELECT * FROM PAYMENT_TABLE

Good approach:

Order Service
→ Calls Payment Service API
→ Receives payment status

This keeps service boundaries intact.

---

Q39: What challenges arise with Database per Service Pattern? (Asked in Amazon, EPAM, Microsoft)

A:
Major challenges are:

* Data consistency
* Distributed transactions
* Data duplication
* Reporting complexity
* More operational management

Example:

Order Service creates an order.

Payment Service fails.

Question:

Should the order exist?

Handling such scenarios becomes more difficult in distributed systems.

This is why patterns like:

* Saga Pattern
* Event-driven architecture
* Eventual consistency

are commonly used in microservices.

---

## Topic 8: Stateless Services

Q40: What is a Stateless Service? (Asked in TCS, Infosys, EPAM, Wipro)

A:
A stateless service does not store client session information inside its memory between requests.

Every request contains all information needed for processing.

Example:

Request:

GET /orders/123
Authorization: JWT Token

The service processes the request and sends the response.

After responding, the service does not remember anything about that client.

Every request is independent.

---

Q41: Why are Stateless Services preferred in Microservices? (Asked in Amazon, Microsoft, EPAM)

A:
Stateless services are easier to:

* Scale
* Deploy
* Recover
* Load balance

Example:

Three instances:

Payment Service Instance 1
Payment Service Instance 2
Payment Service Instance 3

Request 1 goes to Instance 1.
Request 2 goes to Instance 3.

Since no session data is stored in memory, any instance can process any request.

This makes horizontal scaling extremely simple.

---

Q42: What problems occur with Stateful Services? (Asked in Infosys, TCS, Cognizant)

A:
Stateful services store session data in server memory.

Example:

User logs in.

Session information exists only on Server 1.

Next request goes to Server 2.

Server 2 does not know the user's session.

Problems:

* Session management complexity
* Sticky sessions
* Difficult scaling
* Poor fault tolerance

This is why stateless services are generally preferred.

---

Q43: Where should session information be stored in Microservices? (Asked in Amazon, EPAM, IBM)

A:
Session information is usually stored outside the service.

Common approaches:

* JWT Tokens
* Redis
* Distributed Cache
* Database

Example:

User logs in.

Authentication Service generates JWT.

Every request contains the token.

Any service instance can validate the token and process the request.

No session needs to be stored inside service memory.

---

Q44: Why do Kubernetes and Cloud platforms prefer Stateless Services? (Asked in Microsoft, Amazon, EPAM)

A:
Cloud platforms continuously create and destroy containers.

Example:

Payment Service Pod crashes.

Kubernetes immediately starts a new pod.

If the service is stateless:

* New pod starts serving requests immediately.

If the service is stateful:

* Session information may be lost.

Stateless services provide:

* Better scalability
* Better resilience
* Easier container management
* Better fault recovery

---

## Interview Summary to Remember

A good interview answer can be:

"Microservices work best when services are designed around business domains using DDD principles and bounded contexts. Each service should own its data through the database-per-service pattern and should preferably remain stateless to achieve independent deployment, scalability, and fault isolation."

This single statement covers multiple core microservices principles and leaves a strong impression in interviews.

# Phase 1 - Part 4: CAP Theorem Basics and Distributed System Challenges

## Topic 9: CAP Theorem Basics

Q45: What is the CAP Theorem? (Asked in Amazon, Microsoft, EPAM, Infosys, TCS)

A:
CAP Theorem states that a distributed system can guarantee only two out of the following three properties at the same time:

* Consistency (C)
* Availability (A)
* Partition Tolerance (P)

In simple words:

"When a network failure occurs, a distributed system can choose either Consistency or Availability, but not both."

This theorem was proposed by computer scientist Eric Brewer.

---

Q46: What is Consistency in CAP Theorem? (Asked in TCS, Infosys, Cognizant)

A:
Consistency means every user sees the same data at the same time.

Example:

Suppose your bank account balance is ₹10,000.

You withdraw ₹2,000.

After the transaction:

* ATM should show ₹8,000
* Mobile app should show ₹8,000
* Internet banking should show ₹8,000

Every system sees the latest value.

This is called Consistency.

---

Q47: What is Availability in CAP Theorem? (Asked in Infosys, Wipro, Capgemini)

A:
Availability means the system always responds to requests, even if some servers fail.

Example:

Suppose one product server crashes.

Users should still be able to:

* Browse products
* Search items
* View categories

The system may return slightly old data, but it should continue responding.

This is called Availability.

---

Q48: What is Partition Tolerance in CAP Theorem? (Asked in Amazon, EPAM, IBM)

A:
Partition Tolerance means the system continues operating even when network communication between servers is interrupted.

Example:

Suppose we have:

Server A → Mumbai
Server B → Bangalore

Network connectivity between them fails.

The application should still continue operating instead of completely shutting down.

This ability to survive network failures is called Partition Tolerance.

In distributed systems, network failures are inevitable, so Partition Tolerance is generally mandatory.

---

Q49: Why can't a distributed system provide all three properties together? (Asked in Amazon, Microsoft, EPAM)

A:
Suppose:

Server A and Server B cannot communicate because of a network failure.

Now there are two choices:

Option 1:
Stop accepting requests until both servers synchronize.

Result:

* Consistency = Yes
* Availability = No

Option 2:
Continue accepting requests independently.

Result:

* Availability = Yes
* Consistency = No

Because of network partition, achieving all three properties simultaneously is impossible.

This is the fundamental idea behind CAP Theorem.

---

Q50: Why is Partition Tolerance considered mandatory in Microservices? (Asked in Amazon, EPAM, Microsoft)

A:
Microservices communicate through networks.

Networks can fail because of:

* Server crashes
* DNS issues
* Router failures
* Cloud outages
* Timeout issues

Since network failures are unavoidable, distributed systems must tolerate network partitions.

Therefore, practical systems usually choose between:

CP:
Consistency and Partition Tolerance

or

AP:
Availability and Partition Tolerance

Partition Tolerance is almost always required.

---

Q51: Give a real-world example of AP systems. (Asked in Amazon, IBM, EPAM)

A:
Example:

Social media feed.

Suppose you post a new photo.

Your friend may not see the photo immediately because data replication takes time.

However:

* System remains available.
* Users can continue browsing.

Properties:

* Availability = Yes
* Partition Tolerance = Yes
* Consistency = Eventually

This is an AP system.

---

Q52: Give a real-world example of CP systems. (Asked in Microsoft, Amazon, EPAM)

A:
Example:

Banking system.

Suppose you transfer ₹50,000.

The system cannot show:

* ₹50,000 deducted in one server
* ₹50,000 not deducted in another server

All systems must agree on the same balance.

If synchronization is temporarily impossible, some requests may be blocked.

Properties:

* Consistency = Yes
* Partition Tolerance = Yes
* Availability = Reduced

This is a CP system.

---

## Topic 10: Distributed System Challenges

Q53: Why are distributed systems difficult to build? (Asked in Amazon, Microsoft, EPAM, Uber)

A:
Building distributed systems is difficult because components run on different machines and communicate over networks.

Problems include:

* Network failures
* Latency
* Partial failures
* Data consistency
* Distributed transactions
* Message duplication
* Clock synchronization issues
* Monitoring complexity

In a monolithic application:

Function calls happen inside one process.

In distributed systems:

Everything happens over the network.

And networks can fail anytime.

---

Q54: What is Network Latency? (Asked in TCS, Infosys, Amazon)

A:
Latency is the time taken for a request to travel from one service to another.

Example:

Order Service
→ calls Payment Service

If network delay is 500 milliseconds, every request becomes slower.

As the number of service calls increases, overall response time also increases.

This is called network latency.

---

Q55: Why are remote service calls expensive compared to method calls? (Asked in Amazon, EPAM)

A:
Method call:

paymentService.processPayment();

Execution happens inside memory and is extremely fast.

Remote call:

Order Service
→ Network
→ Payment Service

Additional operations occur:

* Data serialization
* Data transmission
* Deserialization
* Network routing
* Security checks

Therefore:

A remote call is significantly slower and can fail.

Interview Tip:

"Never treat network calls like local method calls."

This sentence is highly appreciated by interviewers.

---

Q56: What is Partial Failure in Distributed Systems? (Asked in Amazon, Microsoft, EPAM)

A:
Partial failure means one component fails while other components continue working.

Example:

E-commerce application:

Product Service = Working
Order Service = Working
Payment Service = Failed

Users can:

* Browse products
* Add items to cart

But payments cannot be processed.

Only part of the system has failed.

This is called partial failure.

Distributed systems constantly deal with partial failures.

---

Q57: Why is Data Consistency difficult in Microservices? (Asked in Amazon, EPAM, IBM)

A:
Every service owns its own database.

Example:

Order Service Database
Payment Service Database
Inventory Service Database

Suppose:

Order created successfully.

Payment fails.

Inventory already reserved.

Now multiple databases contain different states.

Keeping data synchronized across independent databases becomes difficult.

This challenge is called Distributed Data Consistency.

---

Q58: What is Eventual Consistency? (Asked in Amazon, Microsoft, EPAM)

A:
Eventual consistency means all systems may not have identical data immediately, but they will become consistent after some time.

Example:

You change your profile picture.

Immediately:

* Mobile app shows new picture.
* Another device still shows old picture.

After a few seconds:
Both show the new picture.

Data eventually becomes consistent.

Many large-scale systems use eventual consistency because it improves availability and scalability.

---

Q59: Why is Monitoring difficult in Microservices? (Asked in EPAM, Infosys, Capgemini)

A:
A single user request may pass through:

API Gateway
→ User Service
→ Order Service
→ Payment Service
→ Notification Service

If an issue occurs:
Developers need logs from multiple services.

Challenges:

* Distributed logs
* Multiple servers
* Multiple databases
* Multiple deployments

This makes debugging and monitoring much harder than monolithic applications.

---

Q60: Why do Microservices need Resilience Patterns? (Asked in Amazon, Microsoft, EPAM)

A:
Because failures are normal in distributed systems.

Examples:

* Network timeout
* Slow service
* Service crash
* Temporary outage

Without resilience mechanisms:

Payment Service fails
→ Order Service fails
→ Entire checkout process fails

Therefore microservices commonly use:

* Retry Pattern
* Circuit Breaker Pattern
* Timeout Pattern
* Fallback Pattern
* Bulkhead Pattern

These patterns help systems recover gracefully from failures.

---

## Most Important Interview Line to Remember

"In distributed systems, the network is unreliable, latency exists, services can fail independently, and data may not remain immediately consistent. Therefore, microservices must be designed for failure from the beginning."

This single sentence demonstrates strong understanding of distributed systems and often leaves a very good impression during microservices interviews.

## Phase 1 Complete Revision (30-Second Answer)

"Microservices divide applications into small, independently deployable services aligned with business domains. They usually follow DDD principles, bounded contexts, database-per-service, and stateless design. Since microservices are distributed systems, they must handle network failures, latency, partial failures, and data consistency challenges while balancing trade-offs defined by the CAP theorem."
