Yes. For Shorts/Reels, keep one question = one concept = 45-60 seconds. Use this format:

**0-5 sec:** Question
**5-10 sec:** One-line definition
**10-40 sec:** Simple example
**40-55 sec:** Interview tip
**55-60 sec:** Quick recap

---

Q1: What is a Lambda Expression? (Asked in TCS, Infosys, Accenture, Cognizant, Capgemini)

A:

A Lambda Expression is an anonymous function introduced in Java 8. It lets us write behavior in a shorter and cleaner way.

Before Java 8:

```java id="9u9dzh"
Runnable r = new Runnable() {
    public void run() {
        System.out.println("Hello");
    }
};
```

Java 8:

```java id="yg1j0g"
Runnable r = () -> System.out.println("Hello");
```

Real-world example:

Suppose you want to print all employee names from a list. Instead of creating separate classes, you can simply use lambda expressions.

Interview Tip:

Whenever you see code that represents behavior or logic, think about Lambda Expressions.

Quick Recap:

"Lambda Expression is an anonymous function that reduces boilerplate code and makes Java code more readable."

---

## Q2: What is a Functional Interface? (Asked in TCS, Infosys, Wipro, Accenture, EPAM)

**A:**

A Functional Interface is an interface that contains exactly one abstract method.

Example:

```java id="c4j0ow"
@FunctionalInterface
interface Calculator {
    int add(int a, int b);
}
```

Implementation:

```java id="86eqf0"
Calculator c = (a, b) -> a + b;
System.out.println(c.add(10, 20));
```

Output:

```text id="otkv1s"
30
```

Real-world example:

Runnable, Comparator, and Callable are all Functional Interfaces.

Interview Tip:

Lambda Expressions work only with Functional Interfaces.

Quick Recap:

"A Functional Interface has only one abstract method and is mainly used with Lambda Expressions."

---

## Q3: What is Stream API? (Asked in TCS, Infosys, Capgemini, Cognizant, Accenture)

**A:**

Stream API is a feature in Java 8 that processes collections in a functional and declarative way.

Example:

```java id="f7up3f"
List<Integer> numbers =
        Arrays.asList(1,2,3,4,5);

numbers.stream()
       .filter(n -> n % 2 == 0)
       .forEach(System.out::println);
```

Output:

```text id="i3jkn1"
2
4
```

Real-world example:

Suppose you have 10,000 employees and need names of employees earning more than 50,000. Stream API can filter and process the data in one line.

Interview Tip:

Remember that Stream does not store data. It only processes data from a source.

Quick Recap:

"Stream API provides filtering, mapping, sorting, and aggregation with less code and better readability."

---

## Q4: What is the difference between Collection and Stream? (Asked in Infosys, TCS, Accenture, Capgemini, EPAM)

**A:**

Collection stores data.

Stream processes data.

Example:

```java id="m4u7ye"
List<String> names =
        Arrays.asList("Ram", "Shyam");

Stream<String> stream =
        names.stream();
```

Collection:

* Stores elements
* Can add and remove data
* Can be traversed multiple times

Stream:

* Does not store data
* Performs operations on data
* Can be consumed only once

Interview Tip:

Collection is like a warehouse that stores products. Stream is like a conveyor belt that processes products.

Quick Recap:

"Collection stores data, whereas Stream processes data."

---

Q5: What is Optional in Java 8? (Asked in TCS, Infosys, Cognizant, Wipro, Accenture)

A:

Optional is a container object that may or may not contain a value.

It was introduced to reduce NullPointerException.

Example:

```java id="6m5wy5"
Optional<String> name =
        Optional.ofNullable(null);

System.out.println(
        name.orElse("Guest"));
```

Output:

```text id="jll9b8"
Guest
```

Real-world example:

Suppose a user profile may not have a middle name. Instead of returning null, we can return Optional.

Interview Tip:

Optional doesn't eliminate null completely, but it forces developers to handle missing values safely.

Quick Recap:

"Optional is a wrapper object introduced to avoid NullPointerException and handle missing values gracefully."
