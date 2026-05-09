# Free Datacenter IPs

{% hint style="info" %}
Integrating the free Datacenter IPs follows the same process as our standard [**Datacenter Proxies**](/products/proxies/datacenter-proxies.md).
{% endhint %}

After registering on our platform, navigate to your dashboard and create a proxy user. This step activates your free plan.

After you create a proxy user, you will be prompted to a pop up with your first test request to receive a random IP. \
Copy it and change the `USERNAME` and `PASSWORD` parameters to your proxy credentials:

```bash
curl -x dc.oxylabs.io:8000 -U "user-USERNAME:PASSWORD" https://ip.oxylabs.io/location
```

Find more code examples in other code languages below:

{% tabs %}
{% tab title="cURL" %}

```sh
curl -x dc.oxylabs.io:8000 -U "user-USERNAME:PASSWORD" https://ip.oxylabs.io/location 
```

{% endtab %}

{% tab title="Python" %}

```python
#pip install requests
import requests

username = 'USERNAME'
password = 'PASSWORD'
proxy = 'dc.oxylabs.io:8000'

proxies = {
   "https": ('https://user-%s:%s@%s' % (username, password, proxy))
}

response=requests.get("https://ip.oxylabs.io/location", proxies=proxies)

print(response.content)
```

{% endtab %}

{% tab title="Node.js" %}

<pre class="language-javascript"><code class="lang-javascript"><strong>//npm install axios
</strong><strong>const axios = require("axios");
</strong>const https = require("https");

const client = axios.create({
    httpsAgent: new https.Agent({
        rejectUnauthorized: false,
    }),
});
const username = 'USERNAME';
const password = 'PASSWORD'

client
    .get("https://ip.oxylabs.io/location", {
        proxy: {
            protocol: "https",
            host: "dc.oxylabs.io",
            port: 8000,
            auth: {
                username: `user-${username}`,
                password: password,
            },
        },
    })
    .then((res) => {
        console.log(res.data);
    })
    .catch((err) => console.error(err));

</code></pre>

{% endtab %}

{% tab title="PHP" %}

```php
<?php

$username = 'USERNAME';
$password = 'PASSWORD';
$proxy = 'dc.oxylabs.io:8000';
$target = 'https://ip.oxylabs.io/location';

$request = curl_init($target);
curl_setopt($request, CURLOPT_RETURNTRANSFER, 1);
curl_setopt($request, CURLOPT_PROXY, $proxy);
curl_setopt($request, CURLOPT_PROXYUSERPWD, "user-$username:$password");
$responseBody = curl_exec($request);
$error = curl_error($request);
curl_close($request);

if ($responseBody !== false) {
    echo 'Response: ' . $responseBody;
} else {
    echo 'Failed to connect to proxy: ' . $error;
}
```

{% endtab %}

{% tab title="Go" %}

```go
package main

import (
	"fmt"
	"io"
	"net/http"
	"net/url"
)

func main() {
	username, password, entry := "USERNAME", "PASSWORD", "dc.oxylabs.io:8000"
	proxy, err := url.Parse(fmt.Sprintf("https://user-%s:%s@%s", username, password, entry))
	if err != nil {
		panic(err)
	}

	transport := &http.Transport{
		Proxy: http.ProxyURL(proxy),
	}
	client := &http.Client{Transport: transport}
	target := "https://ip.oxylabs.io/location"
	response, err := client.Get(target)
	if err != nil {
		panic(err)
	}
	defer response.Body.Close()

	body, err := io.ReadAll(response.Body)
	if err != nil {
		panic(err)
	}

	fmt.Println("Response:")
	fmt.Println(string(body))
}
```

{% endtab %}

{% tab title="Java" %}

```java
package com.example;

import java.io.IOException;
import java.net.URI;
import java.net.URISyntaxException;
import java.util.Base64;

import org.apache.hc.client5.http.fluent.Request;
import org.apache.hc.core5.http.HttpHost;

public class App {
    public static void main(String[] args) throws IOException, URISyntaxException {
        String target = "http://ip.oxylabs.io/location";
        String username = "USERNAME";
        String password = "PASSWORD";
        String proxy = "dc.oxylabs.io:8000";

        URI proxyURI = new URI(String.format("https://user-%s:%s@%s", username, password, proxy));

        String basicAuth = new String(
                Base64.getEncoder()
                        .encode(
                                proxyURI.getUserInfo().getBytes()));
        String response = Request.get(target)
                .addHeader("Proxy-Authorization", "Basic " + basicAuth)
                .viaProxy(HttpHost.create(proxyURI))
                .execute().returnContent().asString();

        System.out.println(response);
    }
}

```

{% endtab %}

{% tab title="C#" %}

```csharp
using System.Net;

// .NET currently does not support HTTPS proxies
var proxy = new WebProxy {
    Address = new Uri("dc.oxylabs.io:8000"),
    Credentials = new NetworkCredential(
        userName: "user-USERNAME",
        password: "PASSWORD"
    )
};

var httpClientHandler = new HttpClientHandler {Proxy = proxy};

using var client = new HttpClient(handler: httpClientHandler, disposeHandler: true);

var result = await client.GetStringAsync("https://ip.oxylabs.io/location");
Console.WriteLine(result);
```

{% endtab %}
{% endtabs %}

### Important Notes:

**No Location Specification Needed**:\
Free IPs are automatically assigned and offer limited geographic options. **All 5 IPs are located within the United States.** Location selection is not available, so you **don’t need to include specific location parameters** in your requests.

**Authentication Methods:**\
You can authenticate using either username and password or IP whitelisting. Regardless of the method you choose, **the fair usage policy applies.**

**Fair usage policy:**\
To ensure the stability of our services and prevent potential traffic abuse, we have implemented the following limitations for the free Datacenter IPs:

* **Traffic Limit:** The free plan includes a collective limit of 5 GB of traffic per user per month across all 5 IPs. Traffic renews monthly.
* **Concurrent Sessions:** You are limited to 20 concurrent threads (sessions) per user to ensure stable service and prevent abuse.
* **Fixed IPs:** The free Datacenter IPs are fixed and cannot be replaced or refreshed. If you require new or different IPs, consider upgrading to a paid plan.


---

# Agent Instructions: Querying This Documentation

If you need additional information that is not directly available in this page, you can query the documentation dynamically by asking a question.

Perform an HTTP GET request on the current page URL with the `ask` query parameter:

```
GET https://developers.oxylabs.io/products/proxies/datacenter-proxies/free-datacenter-ips.md?ask=<question>
```

The question should be specific, self-contained, and written in natural language.
The response will contain a direct answer to the question and relevant excerpts and sources from the documentation.

Use this mechanism when the answer is not explicitly present in the current page, you need clarification or additional context, or you want to retrieve related documentation sections.


代理轮换

# IP Control

{% hint style="info" %}
Pay per IP users can download the proxy list via the [**Proxy List**](/products/proxies/datacenter-proxies/proxy-list.md) **in the Oxylabs dashboard.**&#x20;
{% endhint %}

## Proxy Rotation

Datacenter Proxies support proxy rotation. To use this feature you need to  use port number `8000`. With each new request you will use a **random IP.**&#x20;

**Code examples**

{% tabs %}
{% tab title="cURL" %}

```sh
curl -x dc.oxylabs.io:8000 -U "user-USERNAME:PASSWORD" https://ip.oxylabs.io/location 
```

{% endtab %}

{% tab title="Python" %}

```python
#pip install requests
import requests

username = 'USERNAME'
password = 'PASSWORD'
proxy = 'dc.oxylabs.io:8000'

proxies = {
   "https": ('https://user-%s:%s@%s' % (username, password, proxy))
}

response=requests.get("https://ip.oxylabs.io/location", proxies=proxies)

print(response.content)
```

{% endtab %}

{% tab title="Node.js" %}

```javascript
//npm install axios
const axios = require("axios");
const https = require("https");

const client = axios.create({
    httpsAgent: new https.Agent({
        rejectUnauthorized: false,
    }),
});
const username = 'USERNAME';
const password = 'PASSWORD'

client
    .get("https://ip.oxylabs.io/location", {
        proxy: {
            protocol: "https",
            host: "dc.oxylabs.io",
            port: 8000,
            auth: {
                username: `user-${username}`,
                password: password,
            },
        },
    })
    .then((res) => {
        console.log(res.data);
    })
    .catch((err) => console.error(err));

```

{% endtab %}

{% tab title="PHP" %}

```php
<?php

$username = 'USERNAME';
$password = 'PASSWORD';
$proxy = 'dc.oxylabs.io:8000';
$target = 'https://ip.oxylabs.io/location';

$request = curl_init($target);
curl_setopt($request, CURLOPT_RETURNTRANSFER, 1);
curl_setopt($request, CURLOPT_PROXY, $proxy);
curl_setopt($request, CURLOPT_PROXYUSERPWD, "user-$username:$password");
$responseBody = curl_exec($request);
$error = curl_error($request);
curl_close($request);

if ($responseBody !== false) {
    echo 'Response: ' . $responseBody;
} else {
    echo 'Failed to connect to proxy: ' . $error;
}
```

{% endtab %}

{% tab title="Go" %}

```go
package main

import (
	"fmt"
	"io"
	"net/http"
	"net/url"
)

func main() {
	username, password, entry := "USERNAME", "PASSWORD", "dc.oxylabs.io:8000"
	proxy, err := url.Parse(fmt.Sprintf("https://user-%s:%s@%s", username, password, entry))
	if err != nil {
		panic(err)
	}

	transport := &http.Transport{
		Proxy: http.ProxyURL(proxy),
	}
	client := &http.Client{Transport: transport}
	target := "https://ip.oxylabs.io/location"
	response, err := client.Get(target)
	if err != nil {
		panic(err)
	}
	defer response.Body.Close()

	body, err := io.ReadAll(response.Body)
	if err != nil {
		panic(err)
	}

	fmt.Println("Response:")
	fmt.Println(string(body))
}
```

{% endtab %}

{% tab title="Java" %}

```java
package com.example;

import java.io.IOException;
import java.net.URI;
import java.net.URISyntaxException;
import java.util.Base64;

import org.apache.hc.client5.http.fluent.Request;
import org.apache.hc.core5.http.HttpHost;

public class App {
    public static void main(String[] args) throws IOException, URISyntaxException {
        String target = "http://ip.oxylabs.io/location";
        String username = "USERNAME";
        String password = "PASSWORD";
        String proxy = "dc.oxylabs.io:8000";

        URI proxyURI = new URI(String.format("https://user-%s:%s@%s", username, password, proxy));

        String basicAuth = new String(
                Base64.getEncoder()
                        .encode(
                                proxyURI.getUserInfo().getBytes()));
        String response = Request.get(target)
                .addHeader("Proxy-Authorization", "Basic " + basicAuth)
                .viaProxy(HttpHost.create(proxyURI))
                .execute().returnContent().asString();

        System.out.println(response);
    }
}

```

{% endtab %}

{% tab title="C#" %}

```csharp
using System.Net;

// .NET currently does not support HTTPS proxies
var proxy = new WebProxy {
    Address = new Uri("dc.oxylabs.io:8000"),
    Credentials = new NetworkCredential(
        userName: "user-USERNAME",
        password: "PASSWORD"
    )
};

var httpClientHandler = new HttpClientHandler {Proxy = proxy};

using var client = new HttpClient(handler: httpClientHandler, disposeHandler: true);

var result = await client.GetStringAsync("https://ip.oxylabs.io/location");
Console.WriteLine(result);
```

{% endtab %}
{% endtabs %}

{% hint style="info" %}
For the **pay per IP** billing type, each request will use **a random IP from your Proxy list** via port `8000`.

For the **pay per traffic** billing type, each request will use a **random IP from the full Datacenter proxy pool** via port `8000`.
{% endhint %}

## Static Sessions

Depending on your billing type, you can utilize specific ports to maintain a consistent IP address for your requests.

#### Datacenter Proxies per IP

For the pay per IP billing type, use a specific static port to make requests. You will find port numbers in your [**proxy list**](/products/proxies/datacenter-proxies/proxy-list.md)**.**

Here is an example using a port (`8001`) for a static session:

```bash
curl -x dc.oxylabs.io:8001 -U user-USERNAME:PASSWORD https://ip.oxylabs.io/location 
```

Find more code examples in other code languages below:

{% tabs %}
{% tab title="cURL" %}

```sh
curl -x dc.oxylabs.io:8001 -U user-USERNAME:PASSWORD https://ip.oxylabs.io/location 
```

{% endtab %}

{% tab title="Python" %}

```python
#pip install requests
import requests

username = 'USERNAME'
password = 'PASSWORD'
proxy = 'dc.oxylabs.io:8001'

proxies = {
   "https": ('https://user-%s:%s@%s' % (username, password, proxy))
}

response=requests.get("https://ip.oxylabs.io/location", proxies=proxies)

print(response.content)
```

{% endtab %}

{% tab title="Node.js" %}

```javascript
//npm install axios
const axios = require("axios");
const https = require("https");

const client = axios.create({
    httpsAgent: new https.Agent({
        rejectUnauthorized: false,
    }),
});
const username = 'USERNAME';
const password = 'PASSWORD'

client
    .get("https://ip.oxylabs.io/location", {
        proxy: {
            protocol: "https",
            host: "dc.oxylabs.io",
            port: 8001,
            auth: {
                username: `user-${username}`,
                password: password,
            },
        },
    })
    .then((res) => {
        console.log(res.data);
    })
    .catch((err) => console.error(err));

```

{% endtab %}

{% tab title="PHP" %}

```php
<?php

$username = 'USERNAME';
$password = 'PASSWORD';
$proxy = 'dc.oxylabs.io:8001';
$target = 'https://ip.oxylabs.io/location';

$request = curl_init($target);
curl_setopt($request, CURLOPT_RETURNTRANSFER, 1);
curl_setopt($request, CURLOPT_PROXY, $proxy);
curl_setopt($request, CURLOPT_PROXYUSERPWD, "user-$username:$password");
$responseBody = curl_exec($request);
$error = curl_error($request);
curl_close($request);

if ($responseBody !== false) {
    echo 'Response: ' . $responseBody;
} else {
    echo 'Failed to connect to proxy: ' . $error;
}
```

{% endtab %}

{% tab title="Go" %}

```go
package main

import (
	"fmt"
	"io"
	"net/http"
	"net/url"
)

func main() {
	username, password, entry := "USERNAME", "PASSWORD", "dc.oxylabs.io:8001"
	proxy, err := url.Parse(fmt.Sprintf("https://user-%s:%s@%s", username, password, entry))
	if err != nil {
		panic(err)
	}

	transport := &http.Transport{
		Proxy: http.ProxyURL(proxy),
	}
	client := &http.Client{Transport: transport}
	target := "https://ip.oxylabs.io/location"
	response, err := client.Get(target)
	if err != nil {
		panic(err)
	}
	defer response.Body.Close()

	body, err := io.ReadAll(response.Body)
	if err != nil {
		panic(err)
	}

	fmt.Println("Response:")
	fmt.Println(string(body))
}
```

{% endtab %}

{% tab title="Java" %}

```java
package com.example;

import java.io.IOException;
import java.net.URI;
import java.net.URISyntaxException;
import java.util.Base64;

import org.apache.hc.client5.http.fluent.Request;
import org.apache.hc.core5.http.HttpHost;

public class App {
    public static void main(String[] args) throws IOException, URISyntaxException {
        String target = "http://ip.oxylabs.io/location";
        String username = "USERNAME";
        String password = "PASSWORD";
        String proxy = "dc.oxylabs.io:8001";

        URI proxyURI = new URI(String.format("https://user-%s:%s@%s", username, password, proxy));

        String basicAuth = new String(
                Base64.getEncoder()
                        .encode(
                                proxyURI.getUserInfo().getBytes()));
        String response = Request.get(target)
                .addHeader("Proxy-Authorization", "Basic " + basicAuth)
                .viaProxy(HttpHost.create(proxyURI))
                .execute().returnContent().asString();

        System.out.println(response);
    }
}

```

{% endtab %}

{% tab title="C#" %}

```csharp
using System.Net;

// .NET currently does not support HTTPS proxies
var proxy = new WebProxy {
    Address = new Uri("dc.oxylabs.io:8001"),
    Credentials = new NetworkCredential(
        userName: "user-USERNAME",
        password: "PASSWORD"
    )
};

var httpClientHandler = new HttpClientHandler {Proxy = proxy};

using var client = new HttpClient(handler: httpClientHandler, disposeHandler: true);

var result = await client.GetStringAsync("https://ip.oxylabs.io/location");
Console.WriteLine(result);
```

{% endtab %}
{% endtabs %}

For a rotating or static session in a specific country, refer to [**Select country**](/products/proxies/datacenter-proxies/select-country.md) page.&#x20;

#### Datacenter Proxies per traffic

For the pay per traffic billing type, a static port within the range of `8001` to `63000` (generate a random number within this range) will be used to make requests. Each request will receive a random IP from the pool, **but the IP will remain consistent for the duration of the session.**

Here is an example using a random port (`35467`) for a static session:

```bash
curl -x dc.oxylabs.io:35467 -U user-USERNAME:PASSWORD https://ip.oxylabs.io/location 
```

Find more code examples in other code languages below:

{% tabs %}
{% tab title="cURL" %}

```sh
curl -x dc.oxylabs.io:35467 -U user-USERNAME:PASSWORD https://ip.oxylabs.io/location 
```

{% endtab %}

{% tab title="Python" %}

```python
#pip install requests
import requests

username = 'USERNAME'
password = 'PASSWORD'
proxy = 'dc.oxylabs.io:35467'

proxies = {
   "https": ('https://user-%s:%s@%s' % (username, password, proxy))
}

response=requests.get("https://ip.oxylabs.io/location", proxies=proxies)

print(response.content)
```

{% endtab %}

{% tab title="Node.js" %}

<pre class="language-javascript"><code class="lang-javascript">//npm install axios
<strong>const axios = require("axios");
</strong>const https = require("https");

const client = axios.create({
    httpsAgent: new https.Agent({
        rejectUnauthorized: false,
    }),
});
const username = 'USERNAME';
const password = 'PASSWORD'

client
    .get("https://ip.oxylabs.io/location", {
        proxy: {
            protocol: "https",
            host: "dc.oxylabs.io",
            port: 35467,
            auth: {
                username: `user-${username}`,
                password: password,
            },
        },
    })
    .then((res) => {
        console.log(res.data);
    })
    .catch((err) => console.error(err));

</code></pre>

{% endtab %}

{% tab title="PHP" %}

```php
<?php

$username = 'USERNAME';
$password = 'PASSWORD';
$proxy = 'dc.oxylabs.io:35467';
$target = 'https://ip.oxylabs.io/location';

$request = curl_init($target);
curl_setopt($request, CURLOPT_RETURNTRANSFER, 1);
curl_setopt($request, CURLOPT_PROXY, $proxy);
curl_setopt($request, CURLOPT_PROXYUSERPWD, "user-$username:$password");
$responseBody = curl_exec($request);
$error = curl_error($request);
curl_close($request);

if ($responseBody !== false) {
    echo 'Response: ' . $responseBody;
} else {
    echo 'Failed to connect to proxy: ' . $error;
}
```

{% endtab %}

{% tab title="Go" %}

```go
package main

import (
	"fmt"
	"io"
	"net/http"
	"net/url"
)

func main() {
	username, password, entry := "USERNAME", "PASSWORD", "dc.oxylabs.io:35467"
	proxy, err := url.Parse(fmt.Sprintf("https://user-%s:%s@%s", username, password, entry))
	if err != nil {
		panic(err)
	}

	transport := &http.Transport{
		Proxy: http.ProxyURL(proxy),
	}
	client := &http.Client{Transport: transport}
	target := "https://ip.oxylabs.io/location"
	response, err := client.Get(target)
	if err != nil {
		panic(err)
	}
	defer response.Body.Close()

	body, err := io.ReadAll(response.Body)
	if err != nil {
		panic(err)
	}

	fmt.Println("Response:")
	fmt.Println(string(body))
}
```

{% endtab %}

{% tab title="Java" %}

```java
package com.example;

import java.io.IOException;
import java.net.URI;
import java.net.URISyntaxException;
import java.util.Base64;

import org.apache.hc.client5.http.fluent.Request;
import org.apache.hc.core5.http.HttpHost;

public class App {
    public static void main(String[] args) throws IOException, URISyntaxException {
        String target = "http://ip.oxylabs.io/location";
        String username = "USERNAME";
        String password = "PASSWORD";
        String proxy = "dc.oxylabs.io:35467";

        URI proxyURI = new URI(String.format("https://user-%s:%s@%s", username, password, proxy));

        String basicAuth = new String(
                Base64.getEncoder()
                        .encode(
                                proxyURI.getUserInfo().getBytes()));
        String response = Request.get(target)
                .addHeader("Proxy-Authorization", "Basic " + basicAuth)
                .viaProxy(HttpHost.create(proxyURI))
                .execute().returnContent().asString();

        System.out.println(response);
    }
}

```

{% endtab %}

{% tab title="C#" %}

```csharp
using System.Net;

// .NET currently does not support HTTPS proxies
var proxy = new WebProxy {
    Address = new Uri("dc.oxylabs.io:35467"),
    Credentials = new NetworkCredential(
        userName: "user-USERNAME",
        password: "PASSWORD"
    )
};

var httpClientHandler = new HttpClientHandler {Proxy = proxy};

using var client = new HttpClient(handler: httpClientHandler, disposeHandler: true);

var result = await client.GetStringAsync("https://ip.oxylabs.io/location");
Console.WriteLine(result);
```

{% endtab %}
{% endtabs %}


---

# Agent Instructions: Querying This Documentation

If you need additional information that is not directly available in this page, you can query the documentation dynamically by asking a question.

Perform an HTTP GET request on the current page URL with the `ask` query parameter:

```
GET https://developers.oxylabs.io/products/proxies/datacenter-proxies/ip-control.md?ask=<question>
```

The question should be specific, self-contained, and written in natural language.
The response will contain a direct answer to the question and relevant excerpts and sources from the documentation.

Use this mechanism when the answer is not explicitly present in the current page, you need clarification or additional context, or you want to retrieve related documentation sections.

