Q1: What is Exception Handling in Java? (Asked in TCS, Infosys, Wipro, Accenture, Cognizant)

A:
Exception Handling is a mechanism in Java that helps us handle runtime errors without stopping the entire program.

Imagine you are reading data from a file. If the file is missing, the program should not crash. Instead, it should display a proper message and continue or exit gracefully.

Java provides keywords like try, catch, finally, throw, and throws to handle exceptions.

Good exception handling makes applications more reliable and user-friendly.

---

Q2: What is the difference between Checked and Unchecked Exceptions? (Asked in Capgemini, IBM, Oracle, EPAM)

A:
Checked Exceptions are checked by the compiler.

The compiler forces you to handle them using try-catch or throws.

Examples include IOException and SQLException.

Unchecked Exceptions are not checked during compilation.

They occur because of programming mistakes.

Examples include NullPointerException, ArithmeticException, and ArrayIndexOutOfBoundsException.

Simple rule:
Checked exceptions are expected problems.
Unchecked exceptions usually indicate bugs in the code.

---

Q3: What is the difference between Error and Exception? (Asked in Deloitte, HCL, Infosys)

A:
An Exception represents a problem that an application can handle.

An Error represents a serious problem that applications normally cannot recover from.

Examples of Errors include OutOfMemoryError and StackOverflowError.

Examples of Exceptions include IOException and NumberFormatException.

Errors are usually caused by the JVM or system resources, while Exceptions are generally caused by application logic.

---

Q4: What happens if an exception is not handled? (Asked in TCS, Accenture, Tech Mahindra)

A:
If an exception is not handled, the JVM terminates the current thread.

It prints the exception name, error message, and stack trace.

The remaining code after the exception is not executed.

Example:

```java
public class Demo {
    public static void main(String[] args) {
        int result = 10 / 0;
        System.out.println("Program continues");
    }
}
```

Output:

```text
Exception in thread "main"
java.lang.ArithmeticException: / by zero
```

The second print statement never executes.

---

Q5: Can we have a try block without a catch block? (Asked in Infosys, Wipro, Cognizant)

A:
Yes.

A try block can exist without a catch block if it is followed by a finally block.

Example:

```java
try {
    System.out.println("Inside try");
} finally {
    System.out.println("Cleanup");
}
```

This is commonly used when you want cleanup code to execute regardless of whether an exception occurs.

---

Q6: Can we have a catch block without a try block? (Asked in TCS, IBM)

A:
No.

A catch block must always be associated with a try block.

Writing only a catch block results in a compilation error.

---

Q7: Can we have multiple catch blocks? (Asked in Oracle, Capgemini, EPAM)

A:
Yes.

One try block can have multiple catch blocks.

Each catch block handles a different type of exception.

Example:

```java
try {
    int arr[] = new int[2];
    arr[5] = 10;
} catch (ArithmeticException e) {
    System.out.println("Arithmetic Error");
} catch (ArrayIndexOutOfBoundsException e) {
    System.out.println("Array Error");
}
```

The first matching catch block executes.

---

Q8: Why should child exception catch blocks come before parent exception catch blocks? (Asked in Oracle, Infosys)

A:
Java checks catch blocks from top to bottom.

If the parent exception is written first, it will catch all child exceptions.

Then the child catch block becomes unreachable, causing a compilation error.

Correct order:

```java
catch (FileNotFoundException e) {
}

catch (IOException e) {
}
```

Always write specific exceptions first and generic ones later.

---

Q9: What is the purpose of the finally block? (Asked in Accenture, Cognizant)

A:
The finally block contains cleanup code.

It executes whether an exception occurs or not.

Typical uses include:

Closing files

Closing database connections

Releasing network resources

Unlocking resources

This helps prevent resource leaks.

---

Q10: Does finally always execute? (Asked in IBM, Deloitte)

A:
Almost always.

The finally block executes even if there is a return statement or an exception.

However, it may not execute if:

The JVM crashes.

System.exit() is called.

The machine loses power.

These are rare situations.

---

Q11: Can we write return inside a finally block? (Asked in Oracle, EPAM)

A:
Yes, but it is a very bad practice.

A return inside finally overrides any previous return or exception.

Example:

```java
public static int test() {
    try {
        return 10;
    } finally {
        return 20;
    }
}
```

The method returns 20.

This makes debugging difficult.

Avoid returning from finally.

---

Q12: What is the difference between throw and throws? (Asked in TCS, Infosys, Oracle)

A:
throw is used to explicitly throw an exception object.

throws is used in the method signature to declare possible exceptions.

Example:

```java
throw new IllegalArgumentException("Invalid age");
```

Example:

```java
public void readFile() throws IOException {
}
```

Remember:
throw creates an exception.
throws declares an exception.

---

Q13: Can we throw our own exceptions? (Asked in Wipro, Cognizant)

A:
Yes.

Developers can create custom exceptions according to business requirements.

Example:

```java
throw new Exception("Age cannot be negative");
```

This helps provide meaningful error messages.

---

Q14: What is a Custom Exception? (Asked in Capgemini, Oracle)

A:
A Custom Exception is a user-defined exception.

It is created by extending Exception or RuntimeException.

Example:

```java
class InvalidAgeException extends Exception {

    public InvalidAgeException(String message) {
        super(message);
    }
}
```

Custom exceptions make business validation easier to understand.

---

Q15: Why do we use RuntimeException? (Asked in IBM, EPAM)

A:
RuntimeException represents programming mistakes.

The compiler does not force developers to handle it.

Examples include:

NullPointerException

ArithmeticException

ClassCastException

ArrayIndexOutOfBoundsException

Most developers fix the code instead of catching these exceptions.

---

Q16: What is Stack Trace? (Asked in Infosys, TCS)

A:
A stack trace shows the sequence of method calls that led to an exception.

It helps developers identify exactly where the problem occurred.

Reading stack traces is one of the most important debugging skills in Java.

---

Q17: What is the difference between printStackTrace() and getMessage()? (Asked in Accenture, Oracle)

A:
getMessage() returns only the exception message.

printStackTrace() prints the complete stack trace, including class names, method names, and line numbers.

Use getMessage() for user-friendly logs.

Use printStackTrace() while debugging.

---

Q18: What happens if an exception occurs inside the catch block? (Asked in Deloitte, IBM)

A:
If another exception occurs inside the catch block and is not handled, the JVM terminates the program.

You can use another try-catch inside the catch block if required.

---

Q19: Can a try block exist without finally? (Asked in Wipro, Cognizant)

A:
Yes.

A try block can have only catch blocks.

The finally block is optional.

---

Q20: What happens if both try and finally contain return statements? (Asked in Oracle, TCS)

A:
The return inside finally takes priority.

Example:

```java
try {
    return 1;
} finally {
    return 2;
}
```

The method returns 2.

This is another reason why returning from finally should be avoided.

---

Q21: Can constructors throw exceptions? (Asked in Infosys, IBM)

A:
Yes.

Constructors can throw exceptions if object creation fails.

Example:

```java
public Student() throws Exception {
    throw new Exception("Object creation failed");
}
```

The caller must handle or declare the exception.

---

Q22: Can the main() method throw exceptions? (Asked in Accenture, Oracle)

A:
Yes.

Example:

```java
public static void main(String[] args) throws Exception {
}
```

If an exception occurs and is not handled, the JVM handles it and terminates the application.

---

Q23: What is Exception Propagation? (Asked in Capgemini, TCS)

A:
Exception Propagation means an exception moves from one method to its caller until it is handled.

Example:

Method C throws an exception.

Method B calls Method C.

Method A calls Method B.

If Method B does not handle it, the exception reaches Method A.

If no method handles it, the JVM handles it.

---

Q24: Which exceptions should we catch? (Asked in IBM, EPAM)

A:
Catch only exceptions that your application can recover from.

Avoid catching every exception unnecessarily.

For programming mistakes like NullPointerException, fix the code instead of hiding the problem with catch blocks.

---

Q25: Why is catching Exception considered a bad practice? (Asked in Oracle, Infosys)

A:
Exception is the parent class of almost all exceptions.

Catching it hides the actual problem.

Specific catch blocks make debugging much easier.

Catch Exception only when absolutely necessary.

---

Q26: What is try-with-resources? (Asked in Oracle, Capgemini, Accenture)

A:
Try-with-resources automatically closes resources after use.

Example:

```java
try (BufferedReader br = new BufferedReader(new FileReader("data.txt"))) {
    System.out.println(br.readLine());
}
```

No need to manually close the resource.

It reduces memory leaks and cleaner code.

---

Q27: Which resources can be used in try-with-resources? (Asked in IBM, Oracle)

A:
Any class implementing AutoCloseable can be used.

Examples include:

BufferedReader

Scanner

FileInputStream

Connection

PreparedStatement

The JVM automatically calls close().

---

Q28: What is the benefit of creating meaningful exception messages? (Asked in TCS, Infosys)

A:
Meaningful exception messages make debugging much easier.

Bad message:

"Error"

Good message:

"Customer ID 105 not found in database."

A good message tells exactly what went wrong.

---

Q29: What are exception handling best practices? (Asked in Oracle, Deloitte)

A:
Some important best practices are:

Catch specific exceptions.

Never leave catch blocks empty.

Avoid returning from finally.

Close resources properly.

Use try-with-resources whenever possible.

Create meaningful exception messages.

Log exceptions instead of silently ignoring them.

---

Q30: What is the most common exception handling mistake made by developers? (Asked in TCS, Infosys, Accenture)

A:
One of the biggest mistakes is writing empty catch blocks.

Example:

```java
try {
    int result = 10 / 0;
} catch (Exception e) {
}
```

This completely hides the actual error.

Instead, either log the exception or handle it properly.

Never ignore exceptions because they make debugging production issues extremely difficult.
