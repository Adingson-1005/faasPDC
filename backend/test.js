console.log("Hello from FaaS Runner - Node.js!");

console.log("2 + 2 =", 2 + 2);

console.log("Current time:", new Date().toISOString());

const names = ["Alice", "Bob", "Charlie"];


names.forEach((name, i) => {
  console.log(`${i + 1}. Hello, ${name}!`);
});
