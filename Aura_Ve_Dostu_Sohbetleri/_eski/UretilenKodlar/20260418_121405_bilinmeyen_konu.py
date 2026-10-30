# Konu: bilinmeyen_konu
# Tarih: 2026-04-18 12:14:05.249023
# Bot A (Geliştirici) tarafından üretildi

def fibonacci(n, a=0, b=1):
  if n == 0:
    return a
  elif n == 1:
    return b
  else:
    return fibonacci(n-1, b, a+b)

n = int(input("Dizinin uzunluğunu girin: "))
dizisi = [fibonacci(i) for i in range(n)]
print(f"Fibonacci dizisi: {dizisi}") 

import matplotlib.pyplot as plt

plt.plot(dizisi)
plt.xlabel("Index")
plt.ylabel("Fibonacci Sayısı")
plt.title("Fibonacci Dizisinin Görselleştirmesi")
plt.show()
