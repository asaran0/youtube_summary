
---

Q1: Why is String immutable in Java? (Asked in TCS, Infosys, Accenture, Cognizant, Capgemini, Wipro, Oracle)

A:

String is immutable, meaning once a String object is created, its value cannot be changed.

There are several reasons for this.

First, Security.

Many sensitive values like usernames, passwords, file paths, and database URLs are stored as Strings. If Strings were mutable, someone could change these values after validation, leading to security issues.

Example:

```
String path = "/home/data";
```

If another object changed it to

```
"/etc/password"
```

the application could become vulnerable.

Second, String Pool.

Java stores String literals in a special memory area called the String Pool.

Example:

```
String s1 = "Java";
String s2 = "Java";
```

Both variables point to the same object.

If one object changed, every reference would unexpectedly see the new value.

Third, Thread Safety.

Since Strings never change, multiple threads can safely use the same object without synchronization.

Fourth, HashMap Performance.

Strings are commonly used as keys in HashMap.

Their hashCode is calculated once and cached.

If String were mutable, changing its value would also change its hashCode, making retrieval impossible.

---

Q2: Why is StringBuilder faster than String? (Asked in Amazon, Flipkart, Microsoft, Oracle)

A:

String objects are immutable.

Every concatenation creates a new object.

Example:

```
String s = "Java";
s = s + " Spring";
s = s + " Boot";
```

Here, three different String objects are created.

Now consider StringBuilder.

```
StringBuilder sb = new StringBuilder();
sb.append("Java");
sb.append(" Spring");
sb.append(" Boot");
```

Only one object is modified repeatedly.

This avoids unnecessary object creation.

Therefore StringBuilder is much faster when performing multiple string operations.

---

Q3: What is the difference between == and equals()? (Asked in TCS, Infosys, Capgemini, Deloitte)

A:

The == operator compares references.

equals() compares object content.

Example:

```
String s1 = new String("Java");
String s2 = new String("Java");
```

```
s1 == s2
```

returns false because both objects are different.

```
s1.equals(s2)
```

returns true because both contain the same value.

For interview questions involving Strings, always explain both reference comparison and content comparison.

---

Q4: Can we override a static method? (Asked in Oracle, IBM, Cognizant)

A:

No.

Static methods belong to the class, not the object.

When a child class defines another static method with the same signature, it is called Method Hiding, not Method Overriding.

Example:

```
class Parent{
    static void show(){
        System.out.println("Parent");
    }
}

class Child extends Parent{
    static void show(){
        System.out.println("Child");
    }
}
```

If you call

```
Parent.show();
```

Parent's method executes.

Static methods are resolved during compile time.

Therefore they cannot be overridden.

---

Q5: Can we override a private method? (Asked in Wipro, Infosys)

A:

No.

Private methods are not inherited.

Since the child class cannot access them, there is nothing to override.

If the child defines another private method with the same name, it is an entirely new method.

---

Q6: Why is hashCode() important when overriding equals()? (Asked in Amazon, Oracle, Walmart)

A:

Whenever equals() is overridden, hashCode() should also be overridden.

Reason:

Hash-based collections like HashMap and HashSet first compare hashCode.

Only if hashCodes match does Java call equals().

If two equal objects have different hashCodes, duplicates may appear or retrieval may fail.

Interview Rule:

Equal objects must have equal hashCodes.

---

Q7: Why does HashMap allow one null key but multiple null values? (Asked in Amazon, Oracle)

A:

HashMap internally stores only one bucket for the null key.

If another null key is inserted, it replaces the previous value.

Example:

```
map.put(null,"Java");
map.put(null,"Spring");
```

Result:

```
null -> Spring
```

But values are not required to be unique.

Therefore multiple null values are allowed.

---

Q8: Why is HashMap not thread-safe? (Asked in IBM, Capgemini)

A:

Multiple threads can modify a HashMap simultaneously.

This may cause

* Data inconsistency
* Lost updates
* Infinite loops during resizing (older JDK versions)

For concurrent applications, use

```
ConcurrentHashMap
```

instead.

---

Q9: Difference between fail-fast and fail-safe iterator? (Asked in Oracle, Infosys)

A:

Fail-Fast Iterator

Throws ConcurrentModificationException if the collection changes while iterating.

Examples:

* ArrayList
* HashMap

Fail-Safe Iterator

Works on a copy of the collection.

No exception occurs.

Examples:

* ConcurrentHashMap
* CopyOnWriteArrayList

---

Q10: Why does Java pass everything by value? (Asked in Amazon, Microsoft)

A:

Java always passes a copy of the variable.

For primitive types, the value itself is copied.

For objects, the reference value is copied.

The copied reference still points to the same object.

Therefore object contents can be modified, but the original reference cannot be changed.

This is why Java is always Pass By Value.

---

Q11: Why does finally sometimes not execute? (Asked in Oracle, IBM)

A:

Normally finally always executes.

However, it may not execute in situations like:

* Calling

```
System.exit(0);
```

* JVM crash
* Power failure
* Process killed externally

Otherwise finally always executes.

---

Q12: Why doesn't HashMap use equals() directly? (Asked in Amazon)

A:

Searching every object using equals() would make lookup slow.

Instead,

Step 1

Calculate hashCode.

Step 2

Go directly to the bucket.

Step 3

If multiple objects exist in that bucket, call equals().

This reduces lookup from scanning all elements to checking only a few candidates.

---

Q13: Why is ArrayList retrieval O(1)? (Asked in TCS, Oracle)

A:

ArrayList stores elements in a contiguous array.

Each element has an index.

Java calculates the memory location directly using the index.

Therefore retrieval is constant time, O(1).

---

Q14: Can a constructor be final, static, or abstract? (Asked in Infosys, Wipro)

A:

No.

* Constructor cannot be final because constructors are not inherited.
* Constructor cannot be static because constructors belong to object creation, not the class.
* Constructor cannot be abstract because abstract methods require implementation, while constructors cannot be overridden.

---

Q15: Why is `volatile` not enough for thread safety? (Asked in Amazon, Oracle)

A:

`volatile` guarantees visibility of changes between threads, but it does not make compound operations atomic.

Example:

```java
volatile int count = 0;

count++;   // read -> increment -> write
```

If two threads execute `count++` at the same time, updates can be lost because it's a three-step operation.

Use synchronized blocks, locks, or atomic classes like `AtomicInteger` when atomicity is required.

Here are 20 more tricky Java interview questions that are commonly asked in interviews for 3–10+ years experienced developers. Each answer is concise enough to explain in about 1 minute, making them ideal for YouTube Shorts or interview preparation.

---

#Q16: Why can't we instantiate an abstract class? (Asked in TCS, Infosys, Wipro, Capgemini)

A:

An abstract class represents an incomplete implementation.

It may contain abstract methods that don't have a body.

Since the implementation is incomplete, Java doesn't allow creating its object.

Instead, a child class must implement all abstract methods before an object can be created.

Example:

```java
abstract class Animal {
    abstract void sound();
}
```

This is invalid:

```java
Animal a = new Animal(); // Compilation Error
```

---

#Q17: Can an abstract class have a constructor? (Asked in Oracle, Accenture)

A:

Yes.

Although an abstract class cannot be instantiated directly, its constructor is executed when a subclass object is created.

Example:

```java
abstract class Animal {
    Animal() {
        System.out.println("Animal Constructor");
    }
}

class Dog extends Animal {}
```

Creating

```java
new Dog();
```

first executes the Animal constructor and then the Dog constructor.

---

#Q18: Why can't interface methods be private? (Asked in Infosys, IBM)

A:

Traditionally, interface methods were public because they were meant to be implemented by other classes.

If a method were private, implementing classes couldn't access it.

Since Java 9, private methods are allowed only for sharing common code inside the interface itself.

They cannot be overridden.

---

#Q19: Why are interface variables always public static final? (Asked in Oracle, Cognizant)

A:

An interface represents a contract.

Variables inside an interface are constants shared by all implementations.

Therefore Java automatically makes them:

* public
* static
* final

Example:

```java
interface Test {
    int VALUE = 100;
}
```

is internally treated as

```java
public static final int VALUE = 100;
```

---

#Q20: Why is Object class the parent of every class? (Asked in TCS, Capgemini)

A:

Java needs common functionality for all objects.

Methods like

* toString()
* equals()
* hashCode()
* wait()
* notify()

should be available everywhere.

Therefore every class automatically extends Object.

---

#Q21: Why doesn't Java support multiple inheritance using classes? (Asked in Amazon, Oracle)

A:

To avoid the Diamond Problem.

Example:

```
A
/ \
B   C
 \ /
  D
```

If both B and C override the same method,

Java wouldn't know which version D should inherit.

Instead, Java supports multiple inheritance through interfaces.

---

#Q22: What is the Diamond Problem? (Asked in Infosys, Wipro)

A:

Suppose

```
Vehicle
   |
---------
|       |
Car   Electric
   \   /
 ElectricCar
```

If both parent classes define the same method,

Java becomes confused about which implementation to use.

This ambiguity is called the Diamond Problem.

Java avoids it by not allowing multiple class inheritance.

---

#Q23: Can we overload the main() method? (Asked in TCS, IBM)

A:

Yes.

You can create multiple main methods.

Example:

```java
public static void main(String[] args)

public static void main(int a)
```

However,

the JVM always starts execution from

```java
public static void main(String[] args)
```

The overloaded versions are called only manually.

---

#Q24: Can we override the main() method? (Asked in Oracle)

A:

No.

The main method is static.

Static methods cannot be overridden.

If a child class declares another main method,

it hides the parent's method.

---

#Q25: Why are arrays covariant in Java? (Asked in Amazon)

A:

Java allows

```java
Object[] arr = new String[5];
```

because arrays are covariant.

However,

this may fail at runtime.

Example:

```java
arr[0] = 100;
```

throws

```
ArrayStoreException
```

because the actual array stores Strings.

Generics were introduced to avoid such runtime errors.

---

#Q26: Why are Generics invariant? (Asked in Oracle)

A:

Suppose Java allowed

```java
List<Object> list = new ArrayList<String>();
```

Then we could do

```java
list.add(100);
```

Now a String list would contain an Integer.

To prevent this,

Java makes Generics invariant.

---

#Q27: Why can't we create Generic Arrays? (Asked in Amazon)

A:

Arrays know their actual type at runtime.

Generics use Type Erasure.

Because of this mismatch,

Java doesn't allow

```java
new T[10];
```

or

```java
new List<String>[10];
```

---

#Q28: What is Type Erasure? (Asked in Oracle)

A:

Java removes generic type information during compilation.

Example:

```java
List<String>
```

becomes

```java
List
```

at runtime.

Generics exist only during compile time.

This maintains backward compatibility with older Java versions.

---

#Q29: Why doesn't Java support operator overloading? (Asked in Infosys)

A:

Operator overloading can make code confusing.

Example in C++

```
+ may add numbers
+ may concatenate
+ may perform completely different logic
```

Java avoids ambiguity.

Only the + operator is overloaded for String concatenation.

---

#Q30: Why is String concatenation using '+' slower inside loops? (Asked in Amazon)

A:

Each

```java
s = s + value;
```

creates a new String object.

Inside a loop,

thousands of temporary objects may be created.

Instead,

use

```java
StringBuilder
```

which modifies the same object repeatedly.

---

#Q31: Why does HashMap performance degrade from O(1) to O(n)? (Asked in Oracle)

A:

If many keys generate the same hashCode,

they are stored in the same bucket.

Searching then becomes sequential.

In older JDKs,

lookup became O(n).

Since Java 8,

long linked lists are converted into Red-Black Trees,

improving lookup to O(log n).

---

#Q32: Why shouldn't mutable objects be used as HashMap keys? (Asked in Amazon)

A:

HashMap calculates the bucket using the key's hashCode.

If the key changes after insertion,

its hashCode changes.

The object remains in the old bucket,

so retrieval fails.

Always use immutable objects like String as keys.

---

#Q33: Difference between Comparable and Comparator? (Asked in TCS, Infosys)

A:

Comparable

* Sorting logic is inside the class.
* Uses `compareTo()`.
* Supports only one default sorting order.

Comparator

* Sorting logic is outside the class.
* Uses `compare()`.
* Supports multiple sorting strategies.

Example:

* Comparable → Sort employees by ID.
* Comparator → Sort by salary, age, or name.

---

#Q34: Why does ConcurrentHashMap perform better than Hashtable? (Asked in Oracle, Amazon)

A:

Hashtable locks the entire map for every operation.

ConcurrentHashMap allows multiple threads to access different parts of the map simultaneously, reducing contention and improving throughput.

As a result, it performs much better in multi-threaded applications.

---

#Q35: Why is Optional introduced in Java 8? (Asked in Accenture, Deloitte, Oracle)

A:

`Optional` helps avoid `NullPointerException` by explicitly representing the presence or absence of a value.

Example:

```java
Optional<String> name = Optional.ofNullable(getName());

name.ifPresent(System.out::println);
```

Instead of repeatedly writing null checks, `Optional` encourages safer and more readable code.

---
