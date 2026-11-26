# Waimea report: Wildfrost (wildfrost v0.4.1)

Run in a browser on 2026-11-25T22:33:32.518Z, against Archipelago 0.6.7 and 0.6.8. The index CI remains the authoritative check.

**Stopped early; results below are partial.**

# Unit tests

**Archipelago 0.6.7** — _ionium-ap/Archipelago@f04b3a3 (0.6.7-ionium.1), fuzzer 17227d7_

## ✅ wildfrost v0.4.1

_All unit tests passed._

**Archipelago 0.6.8** — _ionium-ap/Archipelago@2ae0d22 (0.6.8-ionium.1), fuzzer 53686ba_

## ⚠️ wildfrost v0.4.1

_The unit-test run was stopped._

# Fuzzing

_Timeouts were scaled by this browser's speed, measured on Archipelago 0.6.7's TUNIC._

**Archipelago 0.6.7** — _ionium-ap/Archipelago@f04b3a3 (0.6.7-ionium.1), fuzzer 17227d7_

## Fuzz results for wildfrost v0.4.1

### default

```
Success: 3348
Failure: 0
Timeout: 0
Ignored: 1652
Total: 5000
```
**Failure rate**: 0.0%

_Timeout 30 s (CI's 30 s, scaled by calibration)._


### no-restrictive-starts

```
Success: 3349
Failure: 0
Timeout: 0
Ignored: 1651
Total: 5000
```
**Failure rate**: 0.0%

_Timeout 30 s (CI's 30 s, scaled by calibration)._


### ✅ check-collect-accessibility

<details>
<summary>Details</summary>

Fuzz to check that collecting items into a state doesn't reduce accessibility

```
Success: 336
Failure: 0
Timeout: 0
Ignored: 164
Total: 500
```
**Failure rate**: 0.0%

_Timeout 30 s (CI's 30 s, scaled by calibration)._

</details>

### ✅ check-determinism

<details>
<summary>Details</summary>

Fuzz to check for determinism

```
Success: 339
Failure: 0
Timeout: 0
Ignored: 161
Total: 500
```
**Failure rate**: 0.0%

_Timeout 30 s (CI's 30 s, scaled by calibration); 4 worker pairs, each regenerating its seeds in a second interpreter._

</details>

### ✅ check-gerpocalypse

<details>
<summary>Details</summary>

Fuzz to check for issues with GER

```
Success: 500
Failure: 0
Timeout: 0
Ignored: 0
Total: 500
```
**Failure rate**: 0.0%

_Timeout 30 s (CI's 30 s, scaled by calibration)._

</details>

### ✅ check-indirect-conditions

<details>
<summary>Details</summary>

Fuzz to check for missing indirect conditions

```
Success: 324
Failure: 0
Timeout: 0
Ignored: 176
Total: 500
```
**Failure rate**: 0.0%

_Timeout 30 s (CI's 30 s, scaled by calibration)._

</details>

### ✅ check-item-location-count

<details>
<summary>Details</summary>

Fuzz to check that the item count matches the location count

```
Success: 500
Failure: 0
Timeout: 0
Ignored: 0
Total: 500
```
**Failure rate**: 0.0%

_Timeout 30 s (CI's 30 s, scaled by calibration)._

</details>

### ✅ check-lambda-capture

<details>
<summary>Details</summary>

Fuzz to find out if there's some lambda variable capture issues

```
Success: 354
Failure: 0
Timeout: 0
Ignored: 146
Total: 500
```
**Failure rate**: 0.0%

_Timeout 30 s (CI's 30 s, scaled by calibration)._

</details>

### ✅ check-placement-item-location-refs

<details>
<summary>Details</summary>

Fuzz to check if items/locations agree on their placements

```
Success: 343
Failure: 0
Timeout: 0
Ignored: 157
Total: 500
```
**Failure rate**: 0.0%

_Timeout 30 s (CI's 30 s, scaled by calibration)._

</details>

### ✅ check-static-output-placement

<details>
<summary>Details</summary>

Fuzz to check that the world doesn't modify placements in output

```
Success: 364
Failure: 0
Timeout: 0
Ignored: 136
Total: 500
```
**Failure rate**: 0.0%

_Timeout 30 s (CI's 30 s, scaled by calibration)._

</details>

### ✅ check-ut

<details>
<summary>Details</summary>

Fuzz to check for universal tracker support

```
Success: 345
Failure: 0
Timeout: 0
Ignored: 155
Total: 500
```
**Failure rate**: 0.0%

_Timeout 30 s (CI's 30 s, scaled by calibration)._

</details>

**Archipelago 0.6.8** — _ionium-ap/Archipelago@2ae0d22 (0.6.8-ionium.1), fuzzer 53686ba_

## Fuzz results for wildfrost v0.4.1

### ⏭️ default

_Not run: stopped before it started._

### ⏭️ no-restrictive-starts

_Not run: stopped before it started._

### ⏭️ check-collect-accessibility

_Not run: stopped before it started._

### ⏭️ check-determinism

_Not run: stopped before it started._

### ⏭️ check-gerpocalypse

_Not run: stopped before it started._

### ⏭️ check-indirect-conditions

_Not run: stopped before it started._

### ⏭️ check-item-location-count

_Not run: stopped before it started._

### ⏭️ check-lambda-capture

_Not run: stopped before it started._

### ⏭️ check-placement-item-location-refs

_Not run: stopped before it started._

### ⏭️ check-static-output-placement

_Not run: stopped before it started._

### ⏭️ check-ut

_Not run: stopped before it started._
