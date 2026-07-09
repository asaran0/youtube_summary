Q1: What is the difference between a Process and a Thread? (Asked in TCS, Infosys, Accenture, Capgemini, Cognizant)

A:
A Process is an independent program running in memory. Every process has its own memory space, resources, and execution environment.

A Thread is a lightweight unit of execution inside a process. Multiple threads share the same memory and resources of the process.

For example, Google Chrome is one process, but each browser tab may run in a separate thread.

Because threads share memory, communication between them is faster than communication between processes. However, shared memory also introduces synchronization challenges.

---

Q2: What is Multithreading in Java? (Asked in Wipro, IBM, EPAM, Deloitte)

A:
Multithreading means executing multiple threads simultaneously within the same application.

Instead of waiting for one task to finish before starting another, multiple tasks run concurrently.

For example, in a music application:
One thread plays the song.
Another thread downloads the next song.
A third thread updates the user interface.

This improves responsiveness and better utilizes CPU resources.

---

Q3: Why do we use Multithreading? (Asked in Infosys, TCS, HCL)

A:
Multithreading is mainly used to improve application performance and user experience.

Benefits include:
Better CPU utilization.
Faster execution of independent tasks.
Responsive applications.
Background processing without blocking the main thread.

For example, while uploading a file, the user can still continue using the application.

---

Q4: What are the different ways to create a Thread in Java? (Asked in Cognizant, Capgemini, Accenture)

A:
There are mainly two traditional ways.

First, extend the Thread class.

Second, implement the Runnable interface.

Nowadays, using ExecutorService is the preferred approach because it manages thread creation efficiently.

In modern Java applications, Runnable with ExecutorService is considered the best practice.

---

Q5: Which is better, extending Thread or implementing Runnable? (Asked in IBM, Deloitte, Oracle)

A:
Implementing Runnable is generally preferred.

A class can implement Runnable and still extend another class because Java supports only single inheritance.

It also separates the task from the thread that executes it.

This makes the code more reusable, maintainable, and flexible.

---

Q6: What is the life cycle of a Thread? (Asked in TCS, Infosys, Capgemini)

A:
A thread goes through several states.

New.
Runnable.
Running.
Blocked or Waiting.
Timed Waiting.
Terminated.

For example, after creating a thread, it enters the New state.

Calling start() moves it to Runnable.

When CPU schedules it, it starts Running.

If it waits for a lock or another thread, it enters Waiting.

After completing execution, it reaches the Terminated state.

---

Q7: What is the difference between start() and run()? (Asked in Accenture, Cognizant, Wipro)

A:
Calling start() creates a new thread and internally invokes run().

Calling run() directly does not create a new thread.

It simply executes like a normal method.

This is one of the most common interview questions.

Always call start() to execute a task in a separate thread.

---

Q8: Can we start the same thread twice? (Asked in Infosys, Oracle, IBM)

A:
No.

A thread can be started only once.

If start() is called again on the same thread object, Java throws IllegalThreadStateException.

To execute the task again, create a new Thread object.

---

Q9: What happens if run() throws an exception? (Asked in Capgemini, EPAM, Cognizant)

A:
If the exception is not handled, the thread terminates immediately.

Other threads continue running normally.

Only that particular thread stops.

To avoid unexpected termination, exceptions should be handled inside the run() method.

---

Q10: What is Thread Scheduler? (Asked in TCS, Wipro, Infosys)

A:
The Thread Scheduler is part of the JVM.

It decides which thread gets CPU time.

The scheduling algorithm depends on the operating system.

Therefore, the execution order of threads is never guaranteed.

Developers should never write logic assuming a fixed execution sequence.

---

Q11: What is Thread Priority? (Asked in Accenture, IBM, HCL)

A:
Every thread has a priority between 1 and 10.

MIN_PRIORITY is 1.

NORM_PRIORITY is 5.

MAX_PRIORITY is 10.

Higher priority only suggests that a thread should get CPU earlier.

It does not guarantee execution before lower-priority threads.

---

Q12: Does Thread Priority guarantee execution order? (Asked in Oracle, Cognizant)

A:
No.

Priority is only a hint to the scheduler.

Different operating systems handle priorities differently.

Therefore, two threads with different priorities may still execute in any order.

Never depend on priority for application logic.

---

Q13: What is Thread.sleep()? (Asked in Infosys, Capgemini)

A:
Thread.sleep() pauses the currently executing thread for a specified time.

During sleep, the thread does not consume CPU.

After the sleep duration ends, the thread becomes Runnable again.

Sleep never releases synchronized locks.

---

Q14: What is Thread.yield()? (Asked in TCS, Wipro)

A:
yield() tells the scheduler that the current thread is willing to give other threads a chance to execute.

It is only a suggestion.

The scheduler may ignore it.

Therefore, its behavior is platform dependent.

---

Q15: What is join()? (Asked in IBM, Deloitte)

A:
join() makes one thread wait until another thread completes.

For example, the main thread waits for a worker thread to finish before printing the final result.

join() is commonly used when one task depends on another.

---

Q16: What is Daemon Thread? (Asked in Oracle, Cognizant)

A:
Daemon threads run in the background to support user threads.

Examples include garbage collection and monitoring services.

When all user threads finish, JVM automatically terminates daemon threads.

---

Q17: What is User Thread? (Asked in Infosys, Capgemini)

A:
User threads perform the actual application work.

The JVM keeps running as long as at least one user thread is alive.

The application exits only after all user threads complete.

---

Q18: What is Synchronization? (Asked in TCS, Accenture)

A:
Synchronization controls access to shared resources.

It ensures that only one thread executes a critical section at a time.

This prevents inconsistent data and race conditions.

---

Q19: Why is Synchronization needed? (Asked in Cognizant, IBM)

A:
Without synchronization, multiple threads may modify shared data simultaneously.

This can produce incorrect results.

For example, two threads updating the same bank balance may overwrite each other's changes.

Synchronization prevents such problems.

---

Q20: What is a Race Condition? (Asked in Infosys, Oracle)

A:
A race condition occurs when multiple threads access shared data simultaneously and the final result depends on execution timing.

Race conditions are difficult to reproduce because they may happen only under specific timing conditions.

Proper synchronization eliminates race conditions.

---

Q21: What is a Critical Section?

A:
A critical section is the part of code where shared resources are accessed.

Only one thread should execute this section at a time.

This is usually protected using synchronized blocks or locks.

---

Q22: What is the synchronized keyword?

A:
The synchronized keyword ensures that only one thread can execute a synchronized method or block at a time for the same object.

It provides thread safety by acquiring an intrinsic lock.

---

Q23: Difference between synchronized method and synchronized block?

A:
A synchronized method locks the entire method.

A synchronized block locks only the specified block of code.

Synchronized blocks provide better performance because they reduce the locked area.

---

Q24: What object is locked in a synchronized instance method?

A:
The current object, represented by this, is locked.

If multiple threads use the same object, only one thread can execute synchronized methods at a time.

---

Q25: What object is locked in a synchronized static method?

A:
The Class object is locked.

This means all instances of that class share the same lock for static synchronized methods.

Therefore, only one thread can execute any static synchronized method at a time.

---

Q26: What is Deadlock?

A:
Deadlock happens when two or more threads wait forever for each other to release locks.

Since each thread is waiting, none of them can continue.

The application appears to be stuck.

---

Q27: How can Deadlock be avoided?

A:
Always acquire locks in the same order.

Keep synchronized blocks as small as possible.

Avoid nested locking whenever possible.

Use timeout-based locking if available.

---

Q28: What is Livelock?

A:
In livelock, threads are active but cannot make progress.

Instead of waiting, they continuously respond to each other.

The application keeps running but useful work never completes.

---

Q29: What is Starvation?

A:
Starvation occurs when a thread never gets CPU time because other threads continuously get preference.

The thread remains ready but rarely executes.

---

Q30: What is Thread Safety?

A:
Thread safety means an object behaves correctly even when multiple threads access it simultaneously.

Thread-safe classes protect shared data from corruption.

Synchronization and immutable objects help achieve thread safety.

---

Q31: What is volatile?

A:
The volatile keyword ensures that every thread reads the latest value of a variable directly from main memory.

It guarantees visibility but not atomicity.

---

Q32: Can volatile replace synchronized?

A:
No.

volatile only guarantees visibility.

It does not protect multiple operations like increment.

For compound operations, synchronization or locks are still required.

---

Q33: What is Atomicity?

A:
Atomicity means an operation is completed entirely or not at all.

No other thread can see an incomplete state.

AtomicInteger provides atomic increment operations.

---

Q34: What is Visibility?

A:
Visibility means changes made by one thread become visible to other threads.

volatile, synchronized, and locks all provide visibility guarantees.

---

Q35: What is Happens-Before Relationship?

A:
The Happens-Before relationship defines when one thread is guaranteed to see changes made by another thread.

Synchronization, volatile variables, and thread start or join establish this relationship.

---

Q36: What is Reentrant Lock?

A:
ReentrantLock is an advanced locking mechanism.

It provides features like fairness, tryLock(), interruptible locking, and timed locking.

It offers more flexibility than synchronized.

---

Q37: What is tryLock()?

A:
tryLock() attempts to acquire a lock immediately.

If the lock is available, it returns true.

Otherwise, it returns false instead of waiting.

This helps avoid deadlocks.

---

Q38: What is ReadWriteLock?

A:
ReadWriteLock allows multiple readers simultaneously.

However, only one writer can modify data at a time.

This improves performance for read-heavy applications.

---

Q39: What is AtomicInteger?

A:
AtomicInteger provides thread-safe integer operations without using synchronized.

Methods like incrementAndGet() perform atomic updates efficiently.

---

Q40: What is ThreadLocal?

A:
ThreadLocal provides a separate copy of a variable for each thread.

Changes made by one thread are not visible to other threads.

It is commonly used for user sessions and database connections.

---

Q41: What is ExecutorService?

A:
ExecutorService manages a pool of reusable threads.

Instead of creating threads manually, tasks are submitted to the executor.

This improves performance and simplifies thread management.

---

Q42: Why is Thread Pool better than creating threads manually?

A:
Creating threads is expensive.

Thread pools reuse existing threads.

This reduces memory usage, improves performance, and limits excessive thread creation.

---

Q43: What is Callable?

A:
Callable is similar to Runnable.

The difference is that Callable can return a value and throw checked exceptions.

Runnable cannot.

---

Q44: What is Future?

A:
Future represents the result of an asynchronous task.

It allows checking whether the task is complete and retrieving the result later using get().

---

Q45: Difference between Runnable and Callable?

A:
Runnable does not return any result and cannot throw checked exceptions.

Callable returns a value and can throw checked exceptions.

Callable is usually used with ExecutorService.

---

Q46: What is CountDownLatch?

A:
CountDownLatch allows one or more threads to wait until a set of tasks completes.

Each completed task decreases the counter.

When the counter reaches zero, waiting threads continue execution.

---

Q47: What is CyclicBarrier?

A:
CyclicBarrier allows multiple threads to wait until all threads reach the same point.

After everyone arrives, all threads continue together.

Unlike CountDownLatch, it can be reused.

---

Q48: What is Semaphore?

A:
Semaphore controls how many threads can access a resource simultaneously.

For example, if only five database connections are available, a semaphore ensures that only five threads use them at the same time.

---

Q49: What is the difference between wait() and sleep()? (Asked in TCS, Infosys, Oracle)

A:
sleep() belongs to the Thread class.

wait() belongs to the Object class.

sleep() pauses execution but does not release the lock.

wait() releases the lock and waits until another thread calls notify() or notifyAll().

wait() must always be called inside a synchronized block or synchronized method.

---

Q50: Which Multithreading concepts are most frequently asked in interviews? (Asked in Almost Every Java Interview)

A:
The most commonly asked topics are:

Difference between Process and Thread.

start() vs run().

sleep() vs wait().

Synchronization.

volatile keyword.

Deadlock.

Race Condition.

Thread Safety.

ExecutorService.

Runnable vs Callable.

Future.

CountDownLatch.

Semaphore.

Thread Pool.
