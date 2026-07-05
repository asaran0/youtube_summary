Q1: What are the major features introduced in Java 8? (Asked in TCS, Infosys, Accenture, Cognizant, Capgemini, Wipro, EPAM)

A:

Java 8 was one of the biggest releases of Java. It introduced several features that made Java code simpler, more readable, and easier to maintain.

The major features introduced in Java 8 are:

1. Lambda Expressions

* Used to write anonymous functions.
* Reduces boilerplate code.
* Mostly used with Collections and Stream API.

Before Java 8:

```java
Runnable r = new Runnable() {
    @Override
    public void run() {
        System.out.println("Hello");
    }
};
```

Java 8:

```java
Runnable r = () -> System.out.println("Hello");
```

Benefit:
We can write the same logic in fewer lines with better readability.

2. Functional Interfaces

* An interface having only one abstract method.
* Can be implemented using Lambda Expressions.

Example:

```java
@FunctionalInterface
interface Calculator {
    int add(int a, int b);
}
```

3. Stream API

* Provides a functional way to process collections.
* Supports filtering, mapping, sorting, and aggregation.

Example:

```java
List<Integer> numbers = Arrays.asList(1, 2, 3, 4, 5);

numbers.stream()
       .filter(n -> n % 2 == 0)
       .forEach(System.out::println);
```

Output:

```text
2
4
```

Benefit:
Code becomes cleaner and easier to understand.

4. Default Methods in Interfaces

* Interfaces can contain implemented methods.
* Helps in adding new methods without breaking existing implementations.

Example:

```java
interface Vehicle {
    default void start() {
        System.out.println("Vehicle Started");
    }
}
```

5. Static Methods in Interfaces

Example:

```java
interface MathUtil {
    static int square(int n) {
        return n * n;
    }
}
```

Usage:

```java
MathUtil.square(5);
```

6. Method References

* A shorter form of lambda expressions.

Example:

```java
list.forEach(System.out::println);
```

Instead of:

```java
list.forEach(x -> System.out.println(x));
```

7. Optional Class

* Helps avoid NullPointerException.
* Represents a value that may or may not be present.

Example:

```java
Optional<String> name =
        Optional.ofNullable(null);

System.out.println(
        name.orElse("Guest"));
```

Output:

```text
Guest
```

8. Date and Time API

* Introduced immutable date and time classes.

Example:

```java
LocalDate today = LocalDate.now();
LocalTime time = LocalTime.now();

System.out.println(today);
System.out.println(time);
```

Interview Answer:

"Java 8 introduced Lambda Expressions, Functional Interfaces, Stream API, Method References, Optional Class, Default and Static Methods in Interfaces, and the new Date-Time API. These features support functional programming and help developers write cleaner, more maintainable, and less error-prone code."
