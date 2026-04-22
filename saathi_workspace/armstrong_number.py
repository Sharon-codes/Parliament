def is_armstrong(number: int) -> bool:
    digits = str(abs(number))
    power = len(digits)
    total = sum(int(digit) ** power for digit in digits)
    return total == abs(number)

number = int(input("Enter a number: "))
if is_armstrong(number):
    print(f"{number} is an Armstrong number.")
else:
    print(f"{number} is not an Armstrong number.")
