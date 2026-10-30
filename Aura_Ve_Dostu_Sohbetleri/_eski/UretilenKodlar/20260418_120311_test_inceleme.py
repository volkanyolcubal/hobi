# Konu: test_inceleme
# Tarih: 2026-04-18 12:03:11.540984
# Bot A (Geliştirici) tarafından üretildi

def fibonacci(n):
  if n <= 1:
    return n
  else:
    return fibonacci(n-1) + fibonacci(n-2)

n = int(input("Dizinin uzunluğunu girin: "))
dizisi = [fibonacci(i) for i in range(n)]
print(f"Fibonacci dizisi: {dizisi}") 

import matplotlib.pyplot as plt

plt.plot(dizisi)
plt.xlabel("Index")
plt.ylabel("Fibonacci Sayısı")
plt.title("Fibonacci Dizisinin Görselleştirmesi")
plt.show()
