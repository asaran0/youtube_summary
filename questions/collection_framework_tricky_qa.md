Q1: What is the Java Collections Framework? (Asked in TCS, Infosys, Accenture, Capgemini, Cognizant)

A:
The Java Collections Framework is a set of classes and interfaces that helps us store, manage, and process groups of objects efficiently.

Instead of creating our own data structures, Java provides ready-made implementations like ArrayList, LinkedList, HashSet, HashMap, TreeSet, and many more.

It also provides common operations such as adding, removing, searching, sorting, and iterating over elements.

Think of it like a toolbox where every tool is designed for a specific purpose.

If you need fast searching, use HashMap.
If you need ordered data, use TreeMap.
If you need duplicate values, use List.
If you don't want duplicates, use Set.

Choosing the correct collection improves both performance and readability.

---

Q2: What is the difference between Collection and Collections? (Asked in Wipro, HCL, IBM, Deloitte)

A:
Many candidates get confused between Collection and Collections.

Collection is an interface.

It is the root interface of List, Set, and Queue.

Collections is a utility class.

It contains static methods like sort(), reverse(), shuffle(), max(), min(), binarySearch(), and synchronizedCollection().

Remember it this way.

Collection stores data.

Collections performs operations on data.

---

Q3: What is the difference between List and Set? (Asked in Infosys, TCS, Capgemini)

A:
List allows duplicate elements.

Set does not allow duplicate elements.

List maintains insertion order.

HashSet does not guarantee order.

TreeSet keeps elements sorted.

List allows accessing elements using an index.

Set does not support index-based access.

Use List when duplicate values are acceptable.

Use Set when uniqueness is important.

---

Q4: What is the difference between ArrayList and LinkedList? (Asked in Amazon, Oracle, Adobe)

A:
ArrayList uses a dynamic array internally.

LinkedList uses a doubly linked list.

ArrayList provides faster random access because elements are stored continuously.

LinkedList provides faster insertion and deletion in the middle because only node references change.

If your application reads data frequently, use ArrayList.

If it performs many insertions and deletions, LinkedList can be a better choice.

---

Q5: Why is ArrayList faster than LinkedList for searching? (Asked in Microsoft, Oracle)

A:
ArrayList stores elements in contiguous memory.

Using an index, Java can directly calculate the memory location.

This makes access very fast.

LinkedList stores elements as separate nodes.

To reach the 100th element, Java has to travel through previous nodes one by one.

Therefore searching in LinkedList is slower.

---

Q6: Can ArrayList store duplicate values? (Asked in TCS, Cognizant)

A:
Yes.

ArrayList allows duplicate elements.

It also allows multiple null values.

Example:

```java
List<String> list = new ArrayList<>();
list.add("Java");
list.add("Java");
list.add(null);
list.add(null);

System.out.println(list);
```

Output

```text
[Java, Java, null, null]
```

---

Q7: Why is HashSet faster than ArrayList for searching? (Asked in Accenture, IBM)

A:
HashSet internally uses hashing.

When you search for an element, Java calculates its hash value and directly jumps to the correct bucket.

ArrayList searches one element after another.

So for large data, HashSet is much faster.

This is why HashSet is commonly used for fast lookups.

---

Q8: Why does HashSet not allow duplicate values? (Asked in Infosys, Wipro)

A:
HashSet checks the hashCode() and equals() methods before inserting an object.

If another object with the same hash and equal value already exists, the new object is ignored.

Example:

```java
Set<Integer> set = new HashSet<>();

set.add(10);
set.add(10);

System.out.println(set);
```

Output

```text
[10]
```

---

Q9: What is the difference between HashSet and TreeSet? (Asked in Oracle, Adobe)

A:
HashSet stores elements in no particular order.

TreeSet automatically sorts elements.

HashSet is generally faster.

TreeSet is slower because it maintains sorted order using a Red-Black Tree.

Use HashSet when order is not important.

Use TreeSet when sorted data is required.

---

Q10: What is the difference between HashMap and Hashtable? (Asked in IBM, TCS)

A:
HashMap is not synchronized.

Hashtable is synchronized.

HashMap is faster because there is no synchronization overhead.

HashMap allows one null key and multiple null values.

Hashtable does not allow null keys or null values.

Today, HashMap is preferred in most applications.

---

Q11: What is the difference between HashMap and TreeMap? (Asked in Oracle, Capgemini)

A:
HashMap stores data without any order.

TreeMap stores keys in sorted order.

HashMap uses a hash table.

TreeMap uses a Red-Black Tree.

HashMap gives better performance.

TreeMap should be used when sorted keys are required.

---

Q12: Can HashMap have duplicate keys? (Asked in Infosys, Cognizant)

A:
No.

HashMap does not allow duplicate keys.

If you insert the same key again, the old value gets replaced.

Example:

```java
Map<Integer, String> map = new HashMap<>();

map.put(1, "Java");
map.put(1, "Spring");

System.out.println(map);
```

Output

```text
{1=Spring}
```

---

Q13: Can HashMap have duplicate values? (Asked in Wipro)

A:
Yes.

Only keys must be unique.

Values can be duplicated.

Example:

```java
Map<Integer, String> map = new HashMap<>();

map.put(1, "Java");
map.put(2, "Java");

System.out.println(map);
```

Output

```text
{1=Java, 2=Java}
```

---

Q14: Why are keys in HashMap immutable?

A:
Keys should ideally be immutable.

If a key changes after insertion, its hashCode also changes.

HashMap will not be able to find the object in the expected bucket.

This may result in lookup failures.

That is why String is commonly used as a HashMap key.

---

Q15: Why does String make a good HashMap key?

A:
String is immutable.

Its hashCode never changes after creation.

It also correctly implements equals() and hashCode().

This makes searching reliable and efficient.

Therefore String is one of the best choices for HashMap keys.

---

Q16: What is load factor in HashMap?

A:
Load factor determines when HashMap should increase its capacity.

The default load factor is 0.75.

This means when 75 percent of buckets are filled, HashMap automatically resizes itself.

Resizing improves performance by reducing collisions.

---

Q17: What is the default initial capacity of HashMap?

A:
The default initial capacity is 16 buckets.

When the threshold based on the load factor is reached, the capacity becomes 32, then 64, and so on.

---

Q18: What is hashing?

A:
Hashing is a technique that converts an object into a numeric value called a hash code.

Java uses this hash code to determine where the object should be stored.

Hashing helps achieve very fast insertion, deletion, and searching.

---

Q19: What is a hash collision?

A:
A collision happens when two different objects produce the same hash code.

HashMap stores both objects in the same bucket.

Java then uses equals() to identify the correct object.

Collisions reduce performance if they occur frequently.

---

Q20: What is the difference between equals() and hashCode()?

A:
equals() checks whether two objects are logically equal.

hashCode() returns an integer representing the object.

If two objects are equal, their hash codes must also be equal.

However, two objects may have the same hash code and still not be equal.

Both methods must be overridden together for custom objects used in HashMap or HashSet.

Q21: What happens if we override equals() but do not override hashCode()? (Asked in Amazon, Oracle, Adobe)

A:
This is one of the most common interview questions.

If you override equals() but not hashCode(), two objects may be logically equal but produce different hash codes.

HashMap and HashSet first use hashCode() to find the bucket.

If the hash codes are different, Java places the objects into different buckets and never calls equals().

As a result, duplicate objects may get stored in a HashSet or HashMap may fail to find an existing key.

Always remember this rule.

If you override equals(), you must also override hashCode().

---

Q22: What happens if two objects have the same hashCode()? (Asked in Infosys, IBM)

A:
Having the same hashCode does not mean the objects are equal.

Both objects are stored in the same bucket.

Java then uses equals() to determine whether they are actually equal.

If equals() returns true, the existing object is used.

If equals() returns false, both objects are stored.

So, same hashCode does not always mean duplicate objects.

---

Q23: Can two unequal objects have the same hashCode()? (Asked in TCS, Capgemini)

A:
Yes.

This situation is called a hash collision.

For example, two completely different objects may accidentally generate the same hashCode.

Java handles this internally by storing both objects in the same bucket and comparing them using equals().

Therefore, hash collisions are normal and expected.

---

Q24: What is Comparable in Java Collections? (Asked in Cognizant, Wipro)

A:
Comparable is an interface used for natural sorting.

A class implements Comparable when it wants to define its default sorting order.

It contains only one method.

```java
compareTo(T obj)
```

Examples include sorting employees by ID or students by roll number.

Collections.sort() automatically uses compareTo() when no Comparator is provided.

---

Q25: What is Comparator in Java? (Asked in Oracle, Accenture)

A:
Comparator is used for custom sorting.

Unlike Comparable, it does not modify the original class.

You can create multiple Comparator implementations.

For example, you can sort employees by salary, age, name, or experience without changing the Employee class.

Comparator provides more flexibility than Comparable.

---

Q26: What is the difference between Comparable and Comparator? (Asked in Microsoft, Amazon)

A:
Comparable defines the natural ordering of a class.

Comparator defines a custom ordering.

Comparable has one compareTo() method.

Comparator has compare() method.

A class can implement only one Comparable.

But you can create multiple Comparator classes for different sorting requirements.

Use Comparable when there is one default sorting order.

Use Comparator when multiple sorting options are needed.

---

Q27: How does Collections.sort() work internally? (Asked in Oracle, Adobe)

A:
Collections.sort() uses TimSort internally.

TimSort is a combination of Merge Sort and Insertion Sort.

It performs very well for real-world data because it takes advantage of already sorted portions of the list.

TimSort is stable.

This means equal elements keep their original order after sorting.

---

Q28: What is the difference between fail-fast and fail-safe iterator? (Asked in IBM, Infosys)

A:
A fail-fast iterator immediately throws ConcurrentModificationException if the collection is modified while iterating.

Examples include ArrayList and HashMap iterators.

A fail-safe iterator works on a copy of the collection.

It does not throw ConcurrentModificationException.

Examples include CopyOnWriteArrayList and ConcurrentHashMap.

Fail-fast detects problems quickly.

Fail-safe allows safe concurrent modifications.

---

Q29: What is ConcurrentModificationException? (Asked in TCS, Capgemini)

A:
This exception occurs when a collection is modified while another thread or the same thread is iterating over it using a fail-fast iterator.

Example:

```java
List<String> list = new ArrayList<>();

list.add("Java");
list.add("Spring");

for (String s : list) {
    list.remove(s);
}
```

This code throws ConcurrentModificationException.

To safely remove elements, use Iterator.remove().

---

Q30: How do you safely remove elements while iterating? (Asked in Infosys, Cognizant)

A:
Use the Iterator's remove() method.

Example:

```java
List<String> list = new ArrayList<>();

list.add("Java");
list.add("Spring");

Iterator<String> iterator = list.iterator();

while (iterator.hasNext()) {
    String value = iterator.next();

    if (value.equals("Java")) {
        iterator.remove();
    }
}

System.out.println(list);
```

This safely removes the element without throwing ConcurrentModificationException.

---

Q31: What is Iterator in Java?

A:
Iterator is used to traverse elements one by one.

It works with most collection classes.

Important methods are:

hasNext() checks whether another element exists.

next() returns the next element.

remove() removes the current element safely.

Iterator is preferred when elements need to be removed during traversal.

---

Q32: What is ListIterator?

A:
ListIterator is an advanced version of Iterator.

It works only with List implementations.

It can move in both forward and backward directions.

It also supports add(), set(), and remove() operations.

Iterator can move only forward.

ListIterator is useful when editing a list during traversal.

---

Q33: What is the difference between Iterator and ListIterator? (Asked in Accenture, IBM)

A:
Iterator works with all collection types.

ListIterator works only with List.

Iterator moves only forward.

ListIterator moves forward and backward.

Iterator cannot replace elements.

ListIterator supports set() to replace elements.

ListIterator provides more functionality but is limited to List collections.

---

Q34: What is Queue in Java Collections?

A:
Queue follows the First In First Out principle.

The first element inserted is the first one removed.

Common implementations include LinkedList, PriorityQueue, and ArrayDeque.

Queues are commonly used in task scheduling, message processing, and printer management.

---

Q35: What is PriorityQueue? (Asked in Oracle, TCS)

A:
PriorityQueue stores elements according to priority rather than insertion order.

By default, the smallest element has the highest priority.

Example:

```java
PriorityQueue<Integer> queue = new PriorityQueue<>();

queue.add(30);
queue.add(10);
queue.add(20);

System.out.println(queue.poll());
```

Output

```text
10
```

The queue automatically returns the smallest value first.

---

Q36: What is Deque in Java?

A:
Deque stands for Double Ended Queue.

Elements can be inserted and removed from both the front and the rear.

Common implementation is ArrayDeque.

Deque can work as both a Queue and a Stack.

---

Q37: Why is ArrayDeque preferred over Stack? (Asked in Amazon)

A:
Stack is an old legacy class.

ArrayDeque is faster because it has less synchronization overhead.

ArrayDeque also provides better performance for stack operations like push(), pop(), and peek().

Today, Java documentation recommends using ArrayDeque instead of Stack.

---

Q38: What is Vector in Java?

A:
Vector is a dynamic array similar to ArrayList.

The major difference is that Vector is synchronized.

Because of synchronization, Vector is slower than ArrayList.

In modern applications, ArrayList is usually preferred.

---

Q39: What is Stack in Java?

A:
Stack follows the Last In First Out principle.

The last element inserted is the first one removed.

Common operations include push(), pop(), and peek().

Although Stack still exists, ArrayDeque is generally recommended for stack operations because it provides better performance.

---

Q40: What is CopyOnWriteArrayList? (Asked in Oracle, Microsoft)

A:
CopyOnWriteArrayList is a thread-safe collection.

Whenever an element is added or removed, Java creates a new copy of the internal array.

Readers continue using the old array while writers work on the new one.

This makes read operations very fast and safe.

However, write operations are slower because copying the array takes extra time.

It is best suited for applications where reads happen much more frequently than writes.


Q41: What is the difference between synchronized collections and concurrent collections? (Asked in Oracle, Amazon, IBM)

A:
Synchronized collections use a single lock for the entire collection.

This means only one thread can access the collection at a time.

Examples include Collections.synchronizedList() and Collections.synchronizedMap().

Concurrent collections are designed for multiple threads.

They use finer locking or lock-free techniques to improve performance.

Examples include ConcurrentHashMap, CopyOnWriteArrayList, and ConcurrentLinkedQueue.

For multi-threaded applications, concurrent collections usually provide better performance than synchronized collections.

---

Q42: What is ConcurrentHashMap? (Asked in Amazon, Microsoft, Oracle)

A:
ConcurrentHashMap is a thread-safe implementation of Map.

Unlike Hashtable, it does not lock the entire map for every operation.

Instead, multiple threads can read and update different parts of the map simultaneously.

This improves performance in multi-threaded applications.

Another important point is that ConcurrentHashMap does not allow null keys or null values.

It is commonly used in high-performance server applications.

---

Q43: What is the difference between HashMap and ConcurrentHashMap? (Asked in Adobe, Infosys)

A:
HashMap is not thread-safe.

ConcurrentHashMap is thread-safe.

HashMap allows one null key and multiple null values.

ConcurrentHashMap does not allow null keys or null values.

HashMap is suitable for single-threaded applications.

ConcurrentHashMap is designed for multi-threaded environments.

If multiple threads access the same map, ConcurrentHashMap should be preferred.

---

Q44: What is the difference between ArrayList and Vector? (Asked in TCS, Wipro)

A:
Both ArrayList and Vector are dynamic arrays.

ArrayList is not synchronized.

Vector is synchronized.

Because of synchronization, Vector is slower.

ArrayList is preferred in modern applications.

Vector is considered a legacy class and is rarely used in new projects.

---

Q45: What is the difference between remove() and clear() in Collections? (Asked in Cognizant, Capgemini)

A:
remove() deletes a specific element from the collection.

clear() removes every element from the collection.

Example:

```java
List<String> list = new ArrayList<>();

list.add("Java");
list.add("Spring");
list.add("Docker");

list.remove("Spring");

System.out.println(list);

list.clear();

System.out.println(list);
```

Output

```text
[Java, Docker]
[]
```

Use remove() when deleting a single element.

Use clear() when the entire collection should become empty.

---

Q46: What is the difference between size() and capacity() in ArrayList? (Asked in Oracle, IBM)

A:
size() returns the number of elements currently stored in the ArrayList.

Capacity is the size of the internal array that can store elements before resizing is needed.

For example, an ArrayList may have a capacity of 10 but currently contain only 3 elements.

Then:

size = 3

capacity = 10

Capacity increases automatically when more space is required.

There is no direct public method to get the capacity of an ArrayList.

---

Q47: What is the difference between poll(), remove(), peek(), and element() in Queue? (Asked in Amazon, Oracle)

A:
These methods behave differently when the queue is empty.

peek() returns the front element without removing it.

If the queue is empty, it returns null.

element() also returns the front element without removing it.

If the queue is empty, it throws an exception.

poll() removes and returns the front element.

If the queue is empty, it returns null.

remove() removes and returns the front element.

If the queue is empty, it throws an exception.

Remember this simple rule.

peek() and poll() return null when the queue is empty.

element() and remove() throw an exception when the queue is empty.

---

Q48: Why is TreeMap slower than HashMap? (Asked in Microsoft, Oracle)

A:
HashMap uses hashing to locate keys.

Searching usually takes constant time.

TreeMap stores keys in a Red-Black Tree.

Searching requires traversing the tree.

As a result, TreeMap operations usually take logarithmic time.

HashMap is faster.

TreeMap should be chosen only when sorted keys are required.

---

Q49: Why should mutable objects not be used as HashMap keys? (Asked in Adobe, Accenture)

A:
A mutable object can change after it has been inserted into the HashMap.

If the fields used in hashCode() or equals() change, the hash value also changes.

The object remains in its original bucket, but HashMap searches using the new hash value.

As a result, the key may no longer be found.

Example:

```java
class Employee {
    String id;

    Employee(String id) {
        this.id = id;
    }

    @Override
    public int hashCode() {
        return id.hashCode();
    }

    @Override
    public boolean equals(Object obj) {
        if (!(obj instanceof Employee)) {
            return false;
        }
        Employee other = (Employee) obj;
        return id.equals(other.id);
    }
}
```

If the `id` field is modified after inserting the object into a HashMap, retrieving the value may fail.

For this reason, immutable objects such as String are preferred as HashMap keys.

---

Q50: What are the most important Collection Framework interview tips? (Asked in Almost Every Java Interview)

A:
Interviewers are usually checking whether you understand when and why to use each collection.

Keep these points in mind.

Use ArrayList when reading data is more frequent than inserting or deleting.

Use LinkedList when frequent insertions and deletions are required.

Use HashSet when duplicate values should not be allowed.

Use TreeSet when unique elements should also remain sorted.

Use HashMap for fast key-value lookups.

Use TreeMap when keys must stay sorted.

Use ConcurrentHashMap in multi-threaded applications.

Always override both equals() and hashCode() for custom objects used in HashMap or HashSet.

Prefer ArrayDeque instead of the legacy Stack class.

Know the internal data structures, time complexity, and real-world use cases of each collection.

These concepts are asked repeatedly in Java interviews ranging from 2 years to 15+ years of experience, so having a strong understanding of them can significantly improve your interview performance.
