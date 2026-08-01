import httpx
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import CrawlResult
from .serializers import CrawlRequestSerializer, CrawlResultSerializer
from .services import crawl_url


def homepage(request):
    return render(request, "crawler/home.html")


@api_view(["GET"])
def healthz(request):
    return Response({"status": "ok"})


@api_view(["POST"])
@csrf_exempt
def crawl_create(request):
    request_serializer = CrawlRequestSerializer(data=request.data)
    request_serializer.is_valid(raise_exception=True)
    url = request_serializer.validated_data["url"]

    try:
        metadata = crawl_url(url)
        crawl = CrawlResult.objects.create(**metadata)
    except httpx.TimeoutException:
        crawl = CrawlResult.objects.create(
            url=url,
            error="Timed out while fetching the URL. The site may be slow or blocking automated crawlers.",
            page_type="unknown",
        )
        return Response(CrawlResultSerializer(crawl).data, status=status.HTTP_504_GATEWAY_TIMEOUT)
    except httpx.HTTPStatusError as exc:
        crawl = CrawlResult.objects.create(
            url=url,
            status_code=exc.response.status_code,
            final_url=str(exc.response.url),
            error=f"Fetch failed with HTTP {exc.response.status_code}. The site may be blocking automated crawlers.",
            page_type="unknown",
        )
        return Response(CrawlResultSerializer(crawl).data, status=status.HTTP_502_BAD_GATEWAY)
    except httpx.HTTPError as exc:
        crawl = CrawlResult.objects.create(url=url, error=str(exc), page_type="unknown")
        return Response(CrawlResultSerializer(crawl).data, status=status.HTTP_502_BAD_GATEWAY)

    return Response(CrawlResultSerializer(crawl).data, status=status.HTTP_201_CREATED)


@api_view(["GET"])
def crawl_detail(request, pk):
    try:
        crawl = CrawlResult.objects.get(pk=pk)
    except CrawlResult.DoesNotExist:
        return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

    return Response(CrawlResultSerializer(crawl).data)
